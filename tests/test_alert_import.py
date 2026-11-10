"""Planilha modelo de alertas: geração, leitura de volta e importação das regras."""
import pytest
from openpyxl import load_workbook

from core.alert_import import (
    STATUS_ERROR, STATUS_NEW, STATUS_SAME, STATUS_UPDATE, apply_import, build_preview, preview_file,
    template_products, template_rule_rows,
)
from core.stock_alerts import StockAlertStore
from core.stores import STORES
from exports.alert_template_export import FIRST_ROW, export_alert_template_xlsx

CATALOG = {"produtos": [
    {"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "grupo": "VESTUÁRIO MASCULINO", "subclasse": "SUNGA"},
    {"codigo_barras": "7896719480003", "descricao": "SUNGA ADULTO M", "grupo": "VESTUÁRIO MASCULINO", "subclasse": "SUNGA"},
    {"codigo_barras": "0007891", "descricao": "COPO", "grupo": "UTILIDADES", "subclasse": "COPO"},
]}
SNAPSHOT = {"rows": [
    {"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "loja": "Pedras", "quantidade_estoque": 4},
    {"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "loja": "Palmeiras", "quantidade_estoque": 1},
]}


@pytest.fixture
def store(tmp_path):
    return StockAlertStore(tmp_path / "regras.json", tmp_path / "snapshot.json")


def columns(sheet, header=FIRST_ROW - 1):
    return {sheet.cell(header, c).value: c for c in range(1, sheet.max_column + 1) if sheet.cell(header, c).value}


def test_products_sheet_lists_catalog_with_stock_per_store():
    rows = template_products(CATALOG, SNAPSHOT)
    assert [r["descricao"] for r in rows] == ["COPO", "SUNGA ADULTO P", "SUNGA ADULTO M"]
    sunga = rows[1]
    assert sunga["estoque"]["Pedras"] == 4 and sunga["estoque"]["Palmeiras"] == 1
    assert sunga["estoque"]["Sapiranga"] is None  # sem estoque registrado na loja


def test_current_rules_become_rows_grouped_by_code_and_limit():
    rules = [
        {"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "loja": "*", "estoque_minimo": 3},
        {"codigo_barras": "7896719480003", "descricao": "SUNGA ADULTO M", "loja": "Pedras", "estoque_minimo": 2},
        {"codigo_barras": "7896719480003", "descricao": "SUNGA ADULTO M", "loja": "Palmeiras", "estoque_minimo": 2},
    ]
    rows = template_rule_rows(rules)
    assert [(r["codigo_barras"], r["lojas"], r["estoque_minimo"]) for r in rows] == [
        ("7896719470004", ["*"], 3), ("7896719480003", ["Palmeiras", "Pedras"], 2)]


def test_template_has_lookup_formulas_and_prefilled_rules(tmp_path, store):
    store.upsert_rule({"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "loja": "*", "estoque_minimo": 3})
    path = tmp_path / "modelo.xlsx"
    assert export_alert_template_xlsx(path, CATALOG, store.load_rules(), SNAPSHOT) == (3, 1)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Alertas", "Produtos", "Como usar"]
    alerts = wb["Alertas"]
    head = columns(alerts)
    assert list(head)[:6] == ["Código de barras", "Descrição do produto", "Grupo", "Estoque atual",
                              "Estoque mínimo", "Todas as lojas"]
    assert all(s in head for s in STORES) and "Situação" in head
    assert alerts.cell(FIRST_ROW, 1).value == "7896719470004" and alerts.cell(FIRST_ROW, head["Todas as lojas"]).value == "Sim"
    assert alerts.cell(FIRST_ROW, head["Estoque mínimo"]).value == 3
    assert "INDEX(" in alerts.cell(FIRST_ROW + 1, head["Descrição do produto"]).value  # linha livre já preenche sozinha
    assert alerts.cell(FIRST_ROW + 1, 1).number_format == "@"
    products = wb["Produtos"]
    assert products.cell(3, 1).value == "Código de barras" and products.cell(4, 2).value == "COPO"


def test_round_trip_preview_and_import(tmp_path, store):
    store.upsert_rule({"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "loja": "*", "estoque_minimo": 3})
    path = tmp_path / "modelo.xlsx"
    export_alert_template_xlsx(path, CATALOG, store.load_rules(), SNAPSHOT)
    wb = load_workbook(path)
    sheet = wb["Alertas"]
    head = columns(sheet)
    minimum, every = head["Estoque mínimo"], head["Todas as lojas"]
    sheet.cell(FIRST_ROW, minimum, 5)                                     # muda o limite da regra atual
    sheet.cell(FIRST_ROW + 1, 1, 7896719480003)                           # colado como número
    sheet.cell(FIRST_ROW + 1, minimum, 2)
    sheet.cell(FIRST_ROW + 1, head["Pedras"], "Sim")
    sheet.cell(FIRST_ROW + 1, head["Palmeiras"], "sim")
    sheet.cell(FIRST_ROW + 2, 1, "7891")                                  # sem o zero à esquerda
    sheet.cell(FIRST_ROW + 2, minimum, "1")                              # nenhuma loja: vale para todas
    sheet.cell(FIRST_ROW + 3, 1, "123")                                   # não existe
    sheet.cell(FIRST_ROW + 3, minimum, 1)
    sheet.cell(FIRST_ROW + 4, 1, "7896719480003")                         # sem mínimo
    sheet.cell(FIRST_ROW + 5, minimum, 2)                                 # sem código
    sheet.cell(FIRST_ROW + 5, every, "Sim")
    wb.save(path)

    preview = preview_file(path, CATALOG, store.load_rules())
    by_row = {line.linha: line for line in preview.lines}
    assert by_row[FIRST_ROW].status == STATUS_UPDATE and "3 → 5" in by_row[FIRST_ROW].mensagem
    assert (by_row[FIRST_ROW + 1].status, by_row[FIRST_ROW + 1].lojas) == (STATUS_NEW, ["Palmeiras", "Pedras"])
    assert by_row[FIRST_ROW + 1].descricao == "SUNGA ADULTO M"
    assert (by_row[FIRST_ROW + 2].descricao, by_row[FIRST_ROW + 2].lojas) == ("COPO", ["*"])
    assert by_row[FIRST_ROW + 3].mensagem == "Código não está no catálogo."
    assert by_row[FIRST_ROW + 4].mensagem == "Informe o estoque mínimo."
    assert by_row[FIRST_ROW + 5].mensagem == "Falta o código de barras."
    assert preview.count(STATUS_ERROR) == 3 and preview.rules_to_write == 4

    assert apply_import(preview, store) == 4
    rules = {(r["codigo_barras"], r["loja"]): r["estoque_minimo"] for r in store.load_rules()}
    assert rules == {("7896719470004", "*"): 5, ("7896719480003", "Pedras"): 2,
                     ("7896719480003", "Palmeiras"): 2, ("7891", "*"): 1}
    # Importar de novo a mesma planilha não muda nada.
    again = preview_file(path, CATALOG, store.load_rules())
    assert again.rules_to_write == 0 and again.count(STATUS_SAME) == 3


def test_repeated_code_and_store_keeps_the_last_line():
    rows = [(5, "7896719470004", 2, True, []), (6, "7896719470004", 4, True, [])]
    preview = build_preview(rows, CATALOG, [])
    first, last = preview.lines
    assert first.status == STATUS_SAME and "linha 6" in first.mensagem
    assert last.status == STATUS_NEW and last.estoque_minimo == 4


def test_invalid_minimum_values():
    rows = [(5, "7896719470004", -1, True, []), (6, "7896719470004", 2.5, True, []), (7, "7896719470004", "abc", True, [])]
    messages = [line.mensagem for line in build_preview(rows, CATALOG, []).lines]
    assert messages == ["O estoque mínimo precisa ser zero ou mais.",
                        "Use um número inteiro de unidades no estoque mínimo.",
                        "Estoque mínimo inválido: “abc”."]


def test_rule_saved_with_another_description_is_updated_not_duplicated(store):
    store.upsert_rule({"codigo_barras": "7896719470004", "descricao": "SUNGA P ANTIGA", "loja": "Pedras", "estoque_minimo": 1})
    preview = build_preview([(5, "7896719470004", 6, False, ["Pedras"])], CATALOG, store.load_rules())
    assert apply_import(preview, store) == 1
    (rule,) = store.load_rules()
    assert rule["estoque_minimo"] == 6 and rule["descricao"] == "SUNGA P ANTIGA"


def test_unknown_file_is_rejected(tmp_path):
    from openpyxl import Workbook
    path = tmp_path / "outra.xlsx"
    Workbook().save(path)
    with pytest.raises(ValueError, match="planilha modelo"):
        preview_file(path, CATALOG, [])

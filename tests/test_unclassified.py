"""Produtos sem classificação: contagem única, Excel por loja e importação."""
import copy
import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from core import catalog_editor as ce
from core.unclassified import (
    UNCLASSIFIED, ClassificationSuggester, apply_classifications, merge_by_barcode, product_count,
)
from exports.unclassified_export import export_unclassified_xlsx, read_classification_xlsx

CATALOG = {
    "meta": {"lojas": ["Sapiranga", "Palmeiras", "pedras"]},
    "produtos": [
        {"codigo_barras": "111", "grupo": "VESTUARIO FEMININO", "subclasse": "SAIA", "descricao": "SAIA JEANS MIDI",
         "situacao": "ATIVO", "lojas": [{"loja": "Sapiranga", "descricao": "SAIA JEANS MIDI", "quantidade_catalogo": "2", "valor": "59.90"}]},
        {"codigo_barras": "222", "grupo": "BRINQUEDO", "subclasse": "PELUCIA", "descricao": "URSO PELUCIA GRANDE",
         "situacao": "ATIVO", "lojas": [{"loja": "pedras", "descricao": "URSO PELUCIA GRANDE", "quantidade_catalogo": "1", "valor": "39.90"}]},
    ],
}


def _row(code, desc, loja, estoque, vendas, grupo=UNCLASSIFIED, sub=UNCLASSIFIED, status="NORMAL"):
    return {"codigo_barras": code, "descricao": desc, "loja": loja, "grupo": grupo, "subclasse": sub,
            "quantidade_estoque": estoque, "quantidade_vendida": vendas, "valor_vendido": vendas * 10.0,
            "valor_estoque": estoque * 5.0, "preco_compra": 5.0, "preco_venda": 10.0, "status_estoque": status}


def frame():
    return pd.DataFrame([
        _row("789001", "SAIA JEANS CURTA", "Sapiranga", 3, 1),
        _row("789001", "SAIA JEANS CURTA", "Palmeiras", 4, 0, status="CRÍTICO"),
        _row("0789001", "SAIA JEANS CURTA", "pedras", 1, 1),  # mesmo número com zero à esquerda
        _row("789002", "URSO PELUCIA PEQ", "Sapiranga", 2, 0),
        _row("111", "SAIA JEANS MIDI", "Sapiranga", 2, 1, grupo="VESTUARIO FEMININO", sub="SAIA"),
    ])


def test_unclassified_product_counts_once_across_stores():
    df = frame()
    assert product_count(df) == 3  # 2 sem classificação únicos + 1 classificado
    merged = merge_by_barcode(df[df.grupo == UNCLASSIFIED])
    assert [m["codigo_barras"] for m in merged] == ["789001", "789002"]
    saia = merged[0]
    assert saia["lojas"] == ["Palmeiras", "Sapiranga", "pedras"]  # ordem oficial
    assert saia["loja"] == "Palmeiras, Sapiranga, pedras"
    assert saia["quantidade_estoque"] == 8 and saia["quantidade_vendida"] == 2
    assert saia["status_estoque"] == "CRÍTICO"  # o mais grave entre as lojas
    assert len(saia["por_loja"]) == 3


def test_suggester_uses_most_similar_classified_description():
    hint = ClassificationSuggester(CATALOG).suggest("SAIA JEANS CURTA")
    assert hint[:2] == ("VESTUARIO FEMININO", "SAIA")
    assert ClassificationSuggester(CATALOG).suggest("123 456") is None


def test_excel_has_one_tab_per_store_and_round_trips(tmp_path):
    path = tmp_path / "sem_classificacao.xlsx"
    assert export_unclassified_xlsx(path, frame(), CATALOG) == 2
    wb = load_workbook(path)
    assert wb.sheetnames == ["Como usar", "Palmeiras", "Sapiranga", "pedras", "Listas"]
    assert wb["Listas"].sheet_state == "hidden"
    sap = wb["Sapiranga"]
    assert [sap.cell(r, 1).value for r in (5, 6)] == ["789001", "789002"]
    assert sap.cell(5, 4).value == "Palmeiras, pedras"
    # Classifica o urso só na aba Sapiranga e a saia (já sugerida) fica como veio.
    headers = [c.value for c in sap[4]]
    assert headers[-2:] == ["GRUPO", "SUBCLASSE"]
    assert not any("sugerid" in str(h).lower() or "confian" in str(h).lower() for h in headers)
    assert all(sap.cell(r, c).value in (None, "") for r in (5, 6) for c in (9, 10))  # em branco para o cliente
    sap.cell(6, 9, "brinquedo"); sap.cell(6, 10, "pelucia")
    wb.save(path)

    items, warnings = read_classification_xlsx(path)
    assert warnings == []
    by_code = {i["codigo_barras"]: i for i in items}
    assert by_code["789002"]["grupo"] == "BRINQUEDO"
    assert "789001" not in by_code  # não preenchido: fica de fora

    catalog = copy.deepcopy(CATALOG)
    summary = apply_classifications(catalog, items)
    assert summary["erros"] == []
    urso = ce.find_product(catalog, "789002")
    assert (urso["grupo"], urso["subclasse"]) == ("BRINQUEDO", "PELUCIA")
    assert [l["loja"] for l in urso["lojas"]] == ["Sapiranga"]


def test_conflicting_classification_between_tabs_is_reported(tmp_path):
    path = tmp_path / "x.xlsx"
    export_unclassified_xlsx(path, frame(), CATALOG)
    wb = load_workbook(path)
    wb["Sapiranga"].cell(5, 9, "VESTUARIO FEMININO"); wb["Sapiranga"].cell(5, 10, "SAIA")
    wb["Palmeiras"].cell(5, 9, "UTILIDADES"); wb["Palmeiras"].cell(5, 10, "COLCHA")
    wb.save(path)
    items, warnings = read_classification_xlsx(path)
    assert "789001" not in {i["codigo_barras"] for i in items}
    assert len(warnings) == 1 and "789001" in warnings[0]


def test_existing_catalog_code_is_updated_not_duplicated():
    catalog = copy.deepcopy(CATALOG)
    summary = apply_classifications(catalog, [{
        "codigo_barras": "0222", "descricao": "URSO", "grupo": "brinquedo", "subclasse": "PELÚCIA",
        "lojas": [{"loja": "Pedras", "descricao": "URSO", "quantidade_catalogo": 3, "valor": 40}],
    }])
    assert summary["atualizados"] == 1 and summary["cadastrados"] == 0
    assert len(catalog["produtos"]) == 2
    urso = ce.find_product(catalog, "222")
    assert (urso["grupo"], urso["subclasse"]) == ("BRINQUEDO", "PELUCIA")
    assert [l["loja"] for l in urso["lojas"]] == ["pedras"]


def test_real_catalog_suggester_builds():
    path = Path(__file__).resolve().parents[1] / "data" / "catalogo_produtos_estoque_geral.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    hint = ClassificationSuggester(catalog).suggest("LENÇOL CASAL BASICO")
    assert hint is not None


def test_hand_made_sheet_from_the_client_is_imported(tmp_path):
    from openpyxl import Workbook
    import pytest
    from exports.unclassified_export import ClassificationFileError
    wb = Workbook()
    ws = wb.active; ws.title = "Palmeiras"  # sem coluna Loja: a aba diz a loja
    ws.append(["Planilha do cliente"]); ws.append([])
    ws.append(["Cód. Barras", "Produto", "Grupo", "Sub Classe", "Qtd", "Preço"])
    ws.append([7891234567895, "MOCHILA ESCOLAR", "acessórios pessoal", "mochila", 4, "89,90"])
    ws.append([222, "URSO PELUCIA GRANDE", "BRINQUEDO", "PELUCIA", 2, 39.9])
    ws.append([333, "SEM GRUPO AINDA", "", "", 1, 10])
    other = wb.create_sheet("Resumo")
    other.append(["Código de barras", "Descrição", "Grupo", "Subclasse"])  # aba sem loja
    other.append(["444", "TOALHA", "UTILIDADES", "TOALHA"])
    path = tmp_path / "cliente.xlsx"; wb.save(path)

    items, warnings = read_classification_xlsx(path)
    assert warnings == []
    by_code = {i["codigo_barras"]: i for i in items}
    assert set(by_code) == {"7891234567895", "222", "444"}
    mochila = by_code["7891234567895"]
    assert (mochila["grupo"], mochila["subclasse"]) == ("ACESSÓRIOS PESSOAL", "MOCHILA")
    assert mochila["lojas"] == [{"loja": "Palmeiras", "descricao": "MOCHILA ESCOLAR", "quantidade_catalogo": 4.0, "valor": 89.9}]

    catalog = copy.deepcopy(CATALOG)
    summary = apply_classifications(catalog, items)
    assert summary["cadastrados"] == 1 and summary["atualizados"] == 1
    assert len(summary["erros"]) == 1 and "444" in summary["erros"][0] and "sem loja" in summary["erros"][0]
    assert ce.find_product(catalog, "7891234567895")["lojas"][0]["loja"] == "Palmeiras"

    empty = Workbook(); empty.active.append(["Nome", "Telefone"]); bad = tmp_path / "bad.xlsx"; empty.save(bad)
    with pytest.raises(ClassificationFileError):
        read_classification_xlsx(bad)

"""Excel do estoque completo: regra do valor de venda e estrutura do arquivo."""
import math

import pandas as pd
import pytest
from openpyxl import load_workbook

from core.inventory import (
    PRICE_CATALOG, PRICE_ESTIMATED, PRICE_SALES, PRICE_SYSTEM, inventory_rows, sale_price,
)
from exports.inventory_export import export_inventory_xlsx

NAN = float("nan")
CATALOG = {"produtos": [
    {"codigo_barras": "0789003", "grupo": "UTILIDADES", "subclasse": "TOALHA", "descricao": "TOALHA BANHO",
     "lojas": [{"loja": "pedras", "descricao": "TOALHA BANHO", "valor": "19.90"}]},
]}


def _row(code, desc, loja, grupo, sub, estoque, vendida=0, venda=0.0, sistema=0.0, compra=10.0, atual=NAN):
    return {"codigo_barras": code, "descricao": desc, "loja": loja, "grupo": grupo, "subclasse": sub,
            "quantidade_estoque": estoque, "quantidade_vendida": vendida, "preco_venda": venda,
            "preco_venda_sistema": sistema, "preco_venda_atual": atual, "preco_compra": compra,
            "preco_compra_estoque": compra, "status_estoque": "NORMAL"}


def frame():
    return pd.DataFrame([
        _row("789001", "SAIA JEANS", "Palmeiras", "VESTUARIO FEMININO", "SAIA", 4, 2, venda=55.0, sistema=59.9),
        _row("789001", "SAIA JEANS", "Sapiranga", "VESTUARIO FEMININO", "SAIA", -2, 3, venda=59.9, sistema=59.9),
        _row("789002", "BLUSA LISA", "Palmeiras", "VESTUARIO FEMININO", "BLUSA", 3, 1, venda=35.0),
        _row("789003", "TOALHA BANHO", "Pedras", "UTILIDADES", "TOALHA", 5, venda=20.0),          # 2× compra
        _row("789004", "CANECA", "Pedras", "SEM CLASSIFICAÇÃO", "SEM CLASSIFICAÇÃO", 0, venda=24.0),
        _row("0007891", "COPO", "Sitio São João", "UTILIDADES", "COPO", 2, venda=8.0, sistema=8.5),
    ])


def test_price_comes_from_system_then_sales_then_catalog_then_estimate():
    lookup = {("789003", "PEDRAS"): 19.9}
    assert sale_price(_row("1", "A", "Pedras", "", "", 1, 2, venda=55.0, sistema=59.9)) == (59.9, PRICE_SYSTEM)
    assert sale_price(_row("1", "A", "Pedras", "", "", 1, 2, venda=55.0, atual=61.0)) == (61.0, PRICE_SYSTEM)
    assert sale_price(_row("1", "A", "Pedras", "", "", 1, 2, venda=55.0)) == (55.0, PRICE_SALES)
    assert sale_price(_row("789003", "A", "Pedras", "", "", 1, venda=20.0), lookup) == (19.9, PRICE_CATALOG)
    assert sale_price(_row("9", "A", "Pedras", "", "", 1, venda=20.0), lookup) == (20.0, PRICE_ESTIMATED)


def test_analysis_saved_before_this_version_still_uses_the_system_price():
    old = _row("1", "A", "Pedras", "", "", 1, venda=29.99)  # sem venda: preco_venda já é a coluna F
    assert sale_price(old, {}, has_system_column=False) == (29.99, PRICE_SYSTEM)
    estimate = _row("1", "A", "Pedras", "", "", 1, venda=20.0)  # 2 × compra (10)
    assert sale_price(estimate, {}, has_system_column=False) == (20.0, PRICE_ESTIMATED)


def test_rows_sorted_by_group_with_unclassified_last_and_negative_stock_has_no_value():
    rows = inventory_rows(frame(), CATALOG)
    assert rows.grupo.iloc[-1] == "SEM CLASSIFICAÇÃO"
    assert list(rows.grupo.iloc[:2]) == ["UTILIDADES", "UTILIDADES"]
    negative = rows[(rows.codigo_barras == "789001") & (rows.loja == "Sapiranga")].iloc[0]
    assert negative.estoque == -2 and negative.valor_total == 0
    towel = rows[rows.codigo_barras == "789003"].iloc[0]
    assert (towel.preco_venda, towel.origem_preco) == (19.9, PRICE_CATALOG)


def test_build_analysis_keeps_the_system_price():
    from core.matcher import build_analysis
    from core.models import AnalysisConfig
    stock = pd.DataFrame([["789001", "SAIA", 2, 20.0, 59.9]],
                         columns=["codigo_barras", "descricao", "quantidade_estoque", "preco_compra", "preco_venda"])
    sales = pd.DataFrame([["789001", "SAIA", 1, 20.0, 49.9, 49.9]],
                         columns=["codigo_barras", "descricao", "quantidade_vendida", "preco_compra", "preco_venda", "faturamento"])
    out, _ = build_analysis(stock, sales, {"produtos": []}, "Pedras", AnalysisConfig("Pedras", None, None, "", ""))
    row = out.iloc[0]
    assert row.preco_venda == pytest.approx(49.9)          # média das vendas, usada nas margens
    assert row.preco_venda_sistema == pytest.approx(59.9)  # coluna F, usada no Excel
    assert sale_price(row.to_dict()) == (59.9, PRICE_SYSTEM)


def test_workbook_has_summary_groups_general_and_one_sheet_per_store(tmp_path):
    path = tmp_path / "estoque.xlsx"
    assert export_inventory_xlsx(path, frame(), CATALOG, "Análise de outubro") == 5
    wb = load_workbook(path)
    assert wb.sheetnames == ["Resumo", "Por grupo", "Geral", "Sitio São João", "Palmeiras", "Sapiranga", "Pedras"]

    general = wb["Geral"]
    assert [general.cell(5, c).value for c in range(1, 8)] == [
        "Código de barras", "Loja", "Descrição do produto", "Grupo", "Subclasse", "Estoque", "Valor de venda"]
    assert len(general.tables) == 1 and list(general.tables.values())[0].ref == "A5:I11"
    assert general["E3"].value == "=SUBTOTAL(103,A6:A11)"   # contador que segue o filtro
    codes = [general.cell(r, 1).value for r in range(6, 12)]
    assert "0007891" in codes and general.cell(6, 1).number_format == "@"  # zeros à esquerda mantidos
    assert general.conditional_formatting  # destaque da busca

    pedras = wb["Pedras"]
    assert [pedras.cell(r, 3).value for r in (6, 7)] == ["TOALHA BANHO", "CANECA"]

    groups = wb["Por grupo"]
    labels = {groups.cell(r, 1).value: r for r in range(6, groups.max_row + 1)}
    total = labels["TOTAL GERAL"]
    assert groups.cell(total, 3).value == 5                   # produtos (códigos únicos)
    grp, sub, prod = labels["▸  VESTUARIO FEMININO"], labels["SAIA"], labels["SAIA JEANS"]
    assert groups.row_dimensions[grp].outlineLevel == 0 and not groups.row_dimensions[grp].hidden
    assert groups.row_dimensions[sub].outlineLevel == 1 and groups.row_dimensions[sub].hidden
    assert groups.row_dimensions[prod].outlineLevel == 2 and groups.row_dimensions[prod].hidden
    header = {groups.cell(5, c).value: c for c in range(1, groups.max_column + 1)}
    assert groups.cell(prod, header["Palmeiras"]).value == 4
    assert groups.cell(prod, header["Sapiranga"]).value == -2
    assert groups.cell(prod, header["Pedras"]).value == "—"   # produto não existe na loja
    assert groups.sheet_properties.outlinePr.summaryBelow is False

    summary = wb["Resumo"]
    stores = {summary.cell(r, 2).value: r for r in range(9, 16)}
    assert summary.cell(stores["Palmeiras"], 3).value == 2  # produtos na loja
    assert summary.cell(stores["Palmeiras"], 2).hyperlink.location == "'Palmeiras'!A1" or \
        "Palmeiras" in summary.cell(stores["Palmeiras"], 2).hyperlink.target
    assert math.isclose(summary.cell(stores["Total da rede"], 5).value,
                        4 * 59.9 + 3 * 35.0 + 5 * 19.9 + 2 * 8.5)


def test_empty_analysis_still_writes_a_valid_file(tmp_path):
    path = tmp_path / "vazio.xlsx"
    assert export_inventory_xlsx(path, frame().iloc[0:0]) == 0
    assert load_workbook(path).sheetnames[:3] == ["Resumo", "Por grupo", "Geral"]

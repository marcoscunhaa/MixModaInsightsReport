from datetime import datetime, time

import pandas as pd
import pytest

from core.loader import SALES_MAP, SALES_REQUIRED, _standardize
from core.matcher import build_analysis
from core.models import AnalysisConfig
from utils.normalization import to_number


@pytest.mark.parametrize("value, expected", [
    (datetime(1900, 1, 24, 23, 45, 36), 24.99),   # 24,99 com formato h:mm
    (time(12, 0), 0.5),                          # 0,5 vira só hora
    (datetime(1900, 2, 3), 34.0),                # quantidade 34
    (datetime(1937, 10, 12, 18, 14, 24), 13800.76),
    (pd.Timestamp("1900-01-15"), 15.0),
    ("1.234,56", 1234.56),
    (None, 0.0),
])
def test_to_number_undoes_date_formatting(value, expected):
    assert to_number(value) == pytest.approx(expected, abs=1e-6)


def sales_frame(rows):
    """Linhas no layout da planilha: A código, B descrição, C qtd, D compra, E custo, F venda, G faturamento, H lucro."""
    raw = pd.DataFrame([
        [code, desc, qty, buy, qty * buy, sell, revenue, revenue - qty * buy]
        for code, desc, qty, buy, sell, revenue in rows
    ])
    return _standardize(raw, SALES_MAP, SALES_REQUIRED)


def stock_frame(rows):
    return pd.DataFrame(rows, columns=["codigo_barras", "descricao", "quantidade_estoque", "preco_compra", "preco_venda"])


def analyze(stock, sales):
    config = AnalysisConfig("Pedras", None, None, "", "")
    frame, _ = build_analysis(stock, sales, {"produtos": []}, "Pedras", config, None)
    return frame.set_index("descricao")


def test_prices_and_revenue_come_from_sales_sheet():
    sales = sales_frame([
        ("7896722660389", "SQUISHY FIDGET", 34, 15.0, 24.99, 849.66),
        ("7896722660389", "SQUISHY FIDGET", 12, 15.0, 29.99, 359.88),  # mesmo produto, outro preço
        ("7896717230006", "CHINELO ADULTO FEM DE 25", 13, 12.5, 24.99, 324.87),
    ])
    stock = stock_frame([
        ("7896722660389", "SQUISHY FIDGET", 5, 14.0, 29.99),
        ("7896717230006", "CHINELO ADULTO FEM DE 25", 2, 12.5, 26.99),
        ("7890000000001", "PRODUTO SEM VENDA", 3, 10.0, 0),
    ])
    frame = analyze(stock, sales)

    squishy = frame.loc["SQUISHY FIDGET"]
    assert squishy.quantidade_vendida == 46
    assert squishy.valor_vendido == pytest.approx(849.66 + 359.88)          # soma da coluna G
    assert squishy.preco_venda == pytest.approx((849.66 + 359.88) / 46)     # média ponderada da F
    assert squishy.preco_compra == pytest.approx(15.0)                      # coluna D
    assert squishy.valor_estoque == pytest.approx(5 * 14.0)                 # custo do estoque
    assert squishy.margem_unitaria == pytest.approx(squishy.preco_venda - 15.0)

    assert squishy.precos_venda == [
        {"preco_venda": 29.99, "quantidade": 12.0, "faturamento": pytest.approx(359.88)},
        {"preco_venda": 24.99, "quantidade": 34.0, "faturamento": pytest.approx(849.66)},
    ]

    assert squishy.preco_venda_atual == pytest.approx(29.99)                 # coluna F do estoque

    chinelo = frame.loc["CHINELO ADULTO FEM DE 25"]
    assert len(chinelo.precos_venda) == 1
    assert pd.isna(chinelo.preco_venda_atual)                               # um preço só: nada muda
    assert (chinelo.preco_compra, chinelo.preco_venda, chinelo.valor_vendido) == pytest.approx((12.5, 24.99, 324.87))

    unsold = frame.loc["PRODUTO SEM VENDA"]
    assert (unsold.quantidade_vendida, unsold.valor_vendido) == (0, 0)
    assert (unsold.preco_compra, unsold.preco_venda) == pytest.approx((10.0, 20.0))  # regra 2x
    assert unsold.precos_venda == []


def test_old_sales_layout_with_three_columns_still_works():
    sales = _standardize(pd.DataFrame([["7896717230006", "CHINELO ADULTO FEM DE 25", 4]]), SALES_MAP, SALES_REQUIRED)
    stock = stock_frame([("7896717230006", "CHINELO ADULTO FEM DE 25", 2, 12.5, 0)])
    row = analyze(stock, sales).loc["CHINELO ADULTO FEM DE 25"]
    assert (row.preco_compra, row.preco_venda, row.valor_vendido) == pytest.approx((12.5, 25.0, 100.0))


def test_stock_status_zero_and_negative():
    sales = sales_frame([("7896717230006", "CHINELO ADULTO FEM DE 25", 3, 12.5, 24.99, 74.97)])
    stock = stock_frame([
        ("7896717230006", "CHINELO ADULTO FEM DE 25", -2, 12.5, 24.99),
        ("7890000000001", "ZERADO SEM VENDA", 0, 10.0, 0),
        ("7890000000002", "COM ESTOQUE", 1, 10.0, 0),
    ])
    frame = analyze(stock, sales)
    assert frame.loc["CHINELO ADULTO FEM DE 25"].status_estoque == "NEGATIVO"
    assert frame.loc["ZERADO SEM VENDA"].status_estoque == "SEM ESTOQUE"
    assert frame.loc["COM ESTOQUE"].status_estoque == "CRÍTICO"

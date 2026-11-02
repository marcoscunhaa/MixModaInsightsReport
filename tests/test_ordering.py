"""Ordem de exibição: código de barras (menor → maior) e lojas na ordem oficial."""
import pandas as pd

from core.analyzer import sort_products
from core.stores import order_stores, store_rank
from utils.normalization import barcode_sort_key


def test_barcode_sort_is_numeric_and_puts_empty_last():
    codes = ["7896722660008", "", "7896722640005", "100", "0007896722660007", None]
    ordered = sorted(codes, key=barcode_sort_key)
    assert ordered[:4] == ["100", "7896722640005", "0007896722660007", "7896722660008"]
    assert set(ordered[4:]) == {"", None}


def test_stores_follow_official_order_with_any_spelling():
    names = ["pedras", "Mix Cosméticos", "Palmeiras", "SITIO SAO JOAO", "Sapiranga"]
    assert order_stores(names) == ["SITIO SAO JOAO", "Palmeiras", "Sapiranga", "pedras", "Mix Cosméticos"]
    assert store_rank("Cosméticos") == 4
    assert order_stores(["Loja Nova", "Pedras"]) == ["Pedras", "Loja Nova"]


def test_sort_products_by_barcode_then_store():
    df = pd.DataFrame({
        "codigo_barras": ["7896722660008", "7896722640005", "7896722640005"],
        "loja": ["Sitio São João", "Pedras", "Palmeiras"],
    })
    out = sort_products(df)
    assert list(zip(out.codigo_barras, out.loja)) == [
        ("7896722640005", "Palmeiras"), ("7896722640005", "Pedras"), ("7896722660008", "Sitio São João"),
    ]


def test_product_options_one_per_code_sorted_and_searchable():
    from core.analyzer import match_options, product_options
    df = pd.DataFrame({
        "codigo_barras": ["7896722660008", "7896722660005", "7896722660005", "7891000000001"],
        "descricao": ["CONJUNTO RENDA GG", "CONJUNTO RENDA P", "CONJ RENDA P", "CUECA BOXER M"],
        "grupo": ["PECAS INTIMAS"] * 4, "subclasse": ["CONJUNTO", "CONJUNTO", "CONJUNTO", "CUECA"],
        "loja": ["Pedras", "Pedras", "Palmeiras", "Pedras"],
    })
    options = product_options(df)
    assert [o["codigo_barras"] for o in options] == ["7891000000001", "7896722660005", "7896722660008"]
    assert options[1]["descricao"] in ("CONJUNTO RENDA P", "CONJ RENDA P")
    assert [o["codigo_barras"] for o in match_options(options, "conjunto")] == ["7896722660005", "7896722660008"]
    assert [o["codigo_barras"] for o in match_options(options, "renda gg")] == ["7896722660008"]
    assert [o["codigo_barras"] for o in match_options(options, "0000001")] == ["7891000000001"]
    assert len(match_options(options, "")) == 3

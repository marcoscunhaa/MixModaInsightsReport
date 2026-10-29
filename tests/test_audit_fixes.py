"""Regressões encontradas na varredura de bugs."""
import pandas as pd
import pytest

from core import loader
from core.analyzer import filter_analysis
from core.stock_alerts import StockAlertStore


@pytest.fixture
def store(tmp_path):
    return StockAlertStore(tmp_path / "rules.json", tmp_path / "snapshot.json")


def snapshot(store, rows):
    store.save_snapshot([
        {"codigo_barras": c, "descricao": d, "loja": l, "quantidade_estoque": q, "preco_venda": 10}
        for c, d, l, q in rows
    ])


def test_alert_fires_when_store_uses_other_description(store):
    # Catálogo: "FRIGIDEIRA GAMMA 24CM"; planilha de Sapiranga: "FRIGIDEIRA CERAMICA 24CM".
    store.upsert_rule({"codigo_barras": "789000111", "descricao": "FRIGIDEIRA GAMMA 24CM", "loja": "*", "estoque_minimo": 3})
    snapshot(store, [("789000111", "FRIGIDEIRA CERAMICA 24CM", "Sapiranga", 2)])
    alerts = store.evaluate()
    assert len(alerts) == 1 and alerts[0]["descricao"] == "FRIGIDEIRA CERAMICA 24CM"


def test_description_breaks_ties_for_shared_code(store):
    store.upsert_rule({"codigo_barras": "123456", "descricao": "PRODUTO A", "loja": "*", "estoque_minimo": 5})
    snapshot(store, [("123456", "PRODUTO A", "Pedras", 1), ("123456", "PRODUTO B", "Pedras", 0)])
    assert [a["descricao"] for a in store.evaluate()] == ["PRODUTO A"]


def test_store_rule_overrides_all_stores_rule(store):
    store.upsert_rule({"codigo_barras": "123456", "descricao": "X", "loja": "*", "estoque_minimo": 10})
    store.upsert_rule({"codigo_barras": "123456", "descricao": "X", "loja": "Pedras", "estoque_minimo": 1})
    snapshot(store, [("123456", "X", "Pedras", 5), ("123456", "X", "Palmeiras", 5)])
    assert [(a["loja"], a["estoque_minimo"]) for a in store.evaluate()] == [("Palmeiras", 10)]


def raw_sheet(column_c):
    return pd.DataFrame([[f"78900000{i}", f"PRODUTO {i}", c, 1.0, 5.0, 9.99, 5.0, 9.99] for i, c in enumerate(column_c)])


def test_swapped_files_are_rejected(monkeypatch):
    monkeypatch.setattr(loader, "read_raw", lambda path: raw_sheet([3.0] * 10))   # vendas
    with pytest.raises(ValueError, match="VENDAS"):
        loader.load_stock("vendas.xls")
    monkeypatch.setattr(loader, "read_raw", lambda path: raw_sheet(["UN"] * 10))  # estoque
    with pytest.raises(ValueError, match="ESTOQUE"):
        loader.load_sales("estoque.xls")


def test_right_files_still_load(monkeypatch):
    monkeypatch.setattr(loader, "read_raw", lambda path: raw_sheet(["UN"] * 10))
    assert len(loader.load_stock("estoque.xls")) == 10
    monkeypatch.setattr(loader, "read_raw", lambda path: raw_sheet([2.0] * 10))
    assert len(loader.load_sales("vendas.xls")) == 10


def test_search_with_scanner_leading_zeros():
    df = pd.DataFrame({"descricao": ["LENCOL"], "codigo_barras": ["40141247193"], "grupo": ["G"],
                       "subclasse": ["S"], "loja": ["Pedras"], "status_estoque": ["NORMAL"]})
    assert len(filter_analysis(df, busca="0040141247193")) == 1
    assert len(filter_analysis(df, busca="000")) == 0

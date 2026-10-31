import pandas as pd

from core.analyzer import filter_analysis


def frame():
    return pd.DataFrame({
        "descricao": ["A", "B", "C", "D"],
        "codigo_barras": ["1", "2", "3", "4"],
        "grupo": ["G1", "G1", "G2", "G2"],
        "subclasse": ["S", "S", "S", "S"],
        "loja": ["Pedras", "Pedras", "Palmeiras", "Pedras"],
        "status_estoque": ["OUT OF STOCK", "CRITICAL", "NORMAL", "CRITICAL"],
        "quantidade_estoque": [0, -3, 5, 1],
    })


def test_status_filters_zero_and_negative():
    df = frame()
    df["status_estoque"] = ["OUT OF STOCK", "NEGATIVE", "NORMAL", "CRITICAL"]
    assert list(filter_analysis(df, status="NEGATIVE").descricao) == ["B"]
    assert list(filter_analysis(df, status="OUT OF STOCK").descricao) == ["A"]


def test_filter_off_keeps_everything():
    assert len(filter_analysis(frame())) == 4


def test_idle_stock_ranks_unsold_by_quantity():
    from core.analyzer import idle_stock
    df = pd.DataFrame({
        "descricao": ["A", "B", "C", "D", "E"],
        "quantidade_estoque": [5, 40, 12, 0, 30],
        "quantidade_vendida": [0, 0, 0, 0, 3],
        "valor_estoque": [500, 40, 120, 0, 300],
    })
    assert list(idle_stock(df, 2).descricao) == ["B", "C"]
    assert list(idle_stock(df).descricao) == ["B", "C", "A"]


def one(stock, sold, status):
    return pd.DataFrame({"quantidade_estoque": [stock], "quantidade_vendida": [sold], "status_estoque": [status]})


def test_single_product_labels():
    from core.analyzer import single_product_labels
    assert single_product_labels(one(0, 46, "OUT OF STOCK")) == {
        "Active products": "1 PRODUCT", "No sales": "HAS SALES",
        "Stockouts": "OUT OF STOCK", "Critical": "OUT OF STOCK",
    }
    labels = single_product_labels(one(-2, 0, "NEGATIVE"))
    assert (labels["Stockouts"], labels["No sales"]) == ("NEGATIVE STOCK", "NO SALES")
    assert single_product_labels(one(8, 3, "NORMAL"))["Stockouts"] == "IN STOCK"
    assert single_product_labels(pd.concat([one(1, 1, "X"), one(2, 2, "Y")])) == {}


def test_stock_by_store_pivots_units_per_store():
    from core.analyzer import stock_by_store
    df = pd.DataFrame({
        "codigo_barras": ["1", "1", "1", "2", "2"],
        "descricao": ["CAMISA BRANCA G", "CAMISA BRANCA G", "CAMISA BCA G", "CAMISA BRANCA M", "CAMISA BRANCA M"],
        "grupo": ["PRISON SUPPLIES"] * 5, "subclasse": ["WHITE T-SHIRT"] * 5,
        "loja": ["Sapiranga", "Pedras", "Palmeiras", "Sapiranga", "Pedras"],
        "quantidade_estoque": [5, 0, 3, -1, 4],
    })
    table, stores, totals = stock_by_store(df)
    assert stores == ["Palmeiras", "Pedras", "Sapiranga"]
    first = table.iloc[0]
    assert (first.descricao, first.Palmeiras, first.Pedras, first.Sapiranga, first.total) == ("CAMISA BRANCA G", 3, 0, 5, 8)
    second = table.iloc[1]
    assert pd.isna(second.Palmeiras) and second.total == 3          # missing in Palmeiras ≠ zero
    assert totals == {"Palmeiras": 3, "Pedras": 4, "Sapiranga": 4}

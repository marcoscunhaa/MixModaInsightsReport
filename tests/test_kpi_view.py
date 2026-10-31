import pandas as pd

from core.kpi_view import STATUS_OPTIONS, kpi_cards, status_counts


def frame(rows):
    df = pd.DataFrame(rows, columns=["quantidade_estoque", "quantidade_vendida", "status_estoque"])
    df["valor_estoque"] = df.quantidade_estoque * 10.0
    df["valor_vendido"] = df.quantidade_vendida * 20.0
    df["margem_unitaria"] = 10.0
    df["produto_sem_venda"] = df.quantidade_vendida <= 0
    df["ruptura"] = (df.quantidade_estoque <= 0) & (df.quantidade_vendida > 0)
    df["giro"] = 50.0
    return df


def by_key(cards):
    return {c["key"]: c for c in cards}


def test_cards_explain_numbers_and_flag_problems():
    cards = by_key(kpi_cards(frame([(0, 5, "OUT OF STOCK"), (1, 0, "CRITICAL"), (10, 2, "NORMAL"), (8, 0, "NO SALES")])))
    assert len(cards) == 10
    assert cards["Stockouts"]["value"] == "1" and cards["Stockouts"]["tone"] == "bad"
    assert cards["No sales"]["hint"] == "50% of products did not sell"
    assert cards["Critical"]["tone"] == "bad"
    assert cards["Stock value"]["clickable"] and not cards["Potential margin"]["clickable"]


def test_zero_problems_are_green():
    cards = by_key(kpi_cards(frame([(10, 2, "NORMAL"), (5, 1, "NORMAL")])))
    assert cards["Stockouts"]["tone"] == "good" and cards["Stockouts"]["hint"].startswith("✓")
    assert cards["Critical"]["hint"] == "✓ no critical products"


def test_single_product_uses_text():
    cards = by_key(kpi_cards(frame([(0, 46, "OUT OF STOCK")])))
    assert cards["Stockouts"]["value"] == "OUT OF STOCK" and cards["Stockouts"]["tone"] == "bad"
    assert cards["No sales"]["value"] == "HAS SALES" and cards["No sales"]["tone"] == "good"
    assert cards["Active products"]["value"] == "1 PRODUCT"


def test_status_counts_cover_every_option():
    counts = status_counts(frame([(0, 5, "OUT OF STOCK"), (-1, 1, "NEGATIVE"), (0, 0, "OUT OF STOCK")]))
    assert counts == {"OUT OF STOCK": 2, "NEGATIVE": 1, "All statuses": 3}
    assert {value for value, *_ in STATUS_OPTIONS} >= {"NEGATIVE", "OUT OF STOCK", "CRITICAL", "LOW", "NO SALES", "EXCESS", "NORMAL"}


def test_store_list_views_pick_rows_and_metric():
    from core.kpi_view import store_list_view
    df = frame([(0, 5, "OUT OF STOCK"), (1, 0, "CRITICAL"), (10, 2, "NORMAL"), (8, 0, "NO SALES")])
    assert store_list_view("Units sold", df)["value"] == "quantidade_vendida"
    assert len(store_list_view("Units sold", df)["rows"]) == 2
    assert len(store_list_view("No sales", df)["rows"]) == 2
    assert len(store_list_view("Stockouts", df)["rows"]) == 1
    assert store_list_view("Stock value", df)["kind"] == "money"
    assert store_list_view("Stock value", df, "NEGATIVE")["kind"] == "stock"
    revenue = store_list_view("Estimated revenue", df)
    assert (revenue["value"], revenue["kind"], len(revenue["rows"])) == ("valor_vendido", "money", 2)
    assert by_key(kpi_cards(df))["Estimated revenue"]["clickable"]
    assert store_list_view("Potential margin", df) is None

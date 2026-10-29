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
    cards = by_key(kpi_cards(frame([(0, 5, "SEM ESTOQUE"), (1, 0, "CRÍTICO"), (10, 2, "NORMAL"), (8, 0, "SEM VENDA")])))
    assert len(cards) == 10
    assert cards["Em ruptura"]["value"] == "1" and cards["Em ruptura"]["tone"] == "bad"
    assert cards["Sem vendas"]["hint"] == "50% dos produtos não venderam"
    assert cards["Críticos"]["tone"] == "bad"
    assert cards["Valor em estoque"]["clickable"] and not cards["Margem potencial"]["clickable"]


def test_zero_problems_are_green():
    cards = by_key(kpi_cards(frame([(10, 2, "NORMAL"), (5, 1, "NORMAL")])))
    assert cards["Em ruptura"]["tone"] == "good" and cards["Em ruptura"]["hint"].startswith("✓")
    assert cards["Críticos"]["hint"] == "✓ nenhum produto crítico"


def test_single_product_uses_text():
    cards = by_key(kpi_cards(frame([(0, 46, "SEM ESTOQUE")])))
    assert cards["Em ruptura"]["value"] == "SEM ESTOQUE" and cards["Em ruptura"]["tone"] == "bad"
    assert cards["Sem vendas"]["value"] == "COM VENDAS" and cards["Sem vendas"]["tone"] == "good"
    assert cards["Produtos ativos"]["value"] == "1 PRODUTO"


def test_status_counts_cover_every_option():
    counts = status_counts(frame([(0, 5, "SEM ESTOQUE"), (-1, 1, "NEGATIVO"), (0, 0, "SEM ESTOQUE")]))
    assert counts == {"SEM ESTOQUE": 2, "NEGATIVO": 1, "Todos os status": 3}
    assert {value for value, *_ in STATUS_OPTIONS} >= {"NEGATIVO", "SEM ESTOQUE", "CRÍTICO", "BAIXO", "SEM VENDA", "EXCESSO", "NORMAL"}


def test_store_list_views_pick_rows_and_metric():
    from core.kpi_view import store_list_view
    df = frame([(0, 5, "SEM ESTOQUE"), (1, 0, "CRÍTICO"), (10, 2, "NORMAL"), (8, 0, "SEM VENDA")])
    assert store_list_view("Unidades vendidas", df)["value"] == "quantidade_vendida"
    assert len(store_list_view("Unidades vendidas", df)["rows"]) == 2
    assert len(store_list_view("Sem vendas", df)["rows"]) == 2
    assert len(store_list_view("Em ruptura", df)["rows"]) == 1
    assert store_list_view("Valor em estoque", df)["kind"] == "money"
    assert store_list_view("Valor em estoque", df, "NEGATIVO")["kind"] == "stock"
    revenue = store_list_view("Faturamento estimado", df)
    assert (revenue["value"], revenue["kind"], len(revenue["rows"])) == ("valor_vendido", "money", 2)
    assert by_key(kpi_cards(df))["Faturamento estimado"]["clickable"]
    assert store_list_view("Margem potencial", df) is None

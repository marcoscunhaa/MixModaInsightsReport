import pandas as pd

from core.analyzer import filter_analysis


def frame():
    return pd.DataFrame({
        "descricao": ["A", "B", "C", "D"],
        "codigo_barras": ["1", "2", "3", "4"],
        "grupo": ["G1", "G1", "G2", "G2"],
        "subclasse": ["S", "S", "S", "S"],
        "loja": ["Pedras", "Pedras", "Palmeiras", "Pedras"],
        "status_estoque": ["SEM ESTOQUE", "CRÍTICO", "NORMAL", "CRÍTICO"],
        "quantidade_estoque": [0, -3, 5, 1],
    })


def test_status_filters_zero_and_negative():
    df = frame()
    df["status_estoque"] = ["SEM ESTOQUE", "NEGATIVO", "NORMAL", "CRÍTICO"]
    assert list(filter_analysis(df, status="NEGATIVO").descricao) == ["B"]
    assert list(filter_analysis(df, status="SEM ESTOQUE").descricao) == ["A"]


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
    assert single_product_labels(one(0, 46, "SEM ESTOQUE")) == {
        "Produtos ativos": "1 PRODUTO", "Sem vendas": "COM VENDAS",
        "Em ruptura": "SEM ESTOQUE", "Críticos": "SEM ESTOQUE",
    }
    labels = single_product_labels(one(-2, 0, "NEGATIVO"))
    assert (labels["Em ruptura"], labels["Sem vendas"]) == ("ESTOQUE NEGATIVO", "SEM VENDAS")
    assert single_product_labels(one(8, 3, "NORMAL"))["Em ruptura"] == "COM ESTOQUE"
    assert single_product_labels(pd.concat([one(1, 1, "X"), one(2, 2, "Y")])) == {}


def test_stock_by_store_pivots_units_per_store():
    from core.analyzer import stock_by_store
    df = pd.DataFrame({
        "codigo_barras": ["1", "1", "1", "2", "2"],
        "descricao": ["CAMISA BRANCA G", "CAMISA BRANCA G", "CAMISA BCA G", "CAMISA BRANCA M", "CAMISA BRANCA M"],
        "grupo": ["PRESIDIO"] * 5, "subclasse": ["CAMISA BRANCA"] * 5,
        "loja": ["Sapiranga", "Pedras", "Palmeiras", "Sapiranga", "Pedras"],
        "quantidade_estoque": [5, 0, 3, -1, 4],
    })
    table, stores, totals = stock_by_store(df)
    assert stores == ["Palmeiras", "Sapiranga", "Pedras"]          # ordem oficial das lojas
    first = table.iloc[0]
    assert (first.descricao, first.Palmeiras, first.Pedras, first.Sapiranga, first.total) == ("CAMISA BRANCA G", 3, 0, 5, 8)
    second = table.iloc[1]
    assert pd.isna(second.Palmeiras) and second.total == 3          # não existe em Palmeiras ≠ zero
    assert totals == {"Palmeiras": 3, "Pedras": 4, "Sapiranga": 4}


def test_same_product_in_several_stores_is_listed_once():
    import pandas as pd
    from core.analyzer import critical, merge_stores, product_count, product_detail, top_sold

    def row(code, loja, estoque, vendas, status, preco=10.0):
        return {"codigo_barras": code, "descricao": f"PROD {code}", "loja": loja, "grupo": "G", "subclasse": "S",
                "quantidade_estoque": estoque, "quantidade_vendida": vendas, "valor_vendido": vendas * preco,
                "valor_estoque": estoque * 5.0, "preco_compra": 5.0, "preco_venda": preco, "status_estoque": status,
                "giro": 0.0, "cobertura": float("inf"), "ruptura": estoque <= 0 and vendas > 0,
                "risco_ruptura": False, "produto_sem_venda": vendas <= 0, "precos_venda": [{"preco_venda": preco}]}
    df = pd.DataFrame([
        row("10", "Pedras", 2, 30, "BAIXO"),
        row("10", "Sapiranga", 0, 26, "SEM ESTOQUE"),
        row("10", "Sitio São João", 9, 4, "NORMAL"),
        row("10", "Palmeiras", 5, 0, "SEM VENDA"),
        row("20", "Sapiranga", 3, 40, "BAIXO", preco=12.0),
    ])
    m = merge_stores(df)
    assert product_count(df) == 2 and len(m) == 2
    p10 = m[m.codigo_barras == "10"].iloc[0]
    assert p10.loja == "Sitio São João, Palmeiras, Sapiranga, Pedras"  # sempre na ordem oficial
    assert (p10.quantidade_estoque, p10.quantidade_vendida, p10.n_lojas) == (16, 60, 4)
    assert p10.status_estoque == "SEM ESTOQUE"  # o mais grave entre as lojas
    assert p10.giro == 60 / 76 * 100
    # Produto de uma loja só fica como veio (inclusive os preços por faixa).
    p20 = m[m.codigo_barras == "20"].iloc[0]
    assert p20.loja == "Sapiranga" and p20.precos_venda == [{"preco_venda": 12.0}]
    # Ranking: o produto 10 soma 60 vendas e aparece uma vez só, à frente do 20.
    assert top_sold(m, 5).codigo_barras.tolist() == ["10", "20"]
    assert critical(m).codigo_barras.tolist().count("10") == 1

    detail = product_detail(df, "10")
    assert [e["loja"] for e in detail["por_loja"]] == ["Sitio São João", "Palmeiras", "Sapiranga", "Pedras"]
    assert [e["status_estoque"] for e in detail["por_loja"]] == ["NORMAL", "SEM VENDA", "SEM ESTOQUE", "BAIXO"]
    assert detail["lojas"] == ["Sitio São João", "Palmeiras", "Sapiranga", "Pedras"]

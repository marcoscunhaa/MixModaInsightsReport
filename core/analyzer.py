import pandas as pd

from core.stores import order_stores, store_sort_key
from utils.normalization import barcode_sort_key

def filter_analysis(df,loja="Todas",grupo="Todos",subclasse="Todas",busca="",status="Todos"):
    out=df
    if loja!="Todas":out=out[out.loja==loja]
    if grupo!="Todos":out=out[out.grupo==grupo]
    if subclasse!="Todas":out=out[out.subclasse==subclasse]
    if status!="Todos":out=out[out.status_estoque==status]
    if busca.strip():
        q=busca.strip().upper()
        m=(out.descricao.str.upper().str.contains(q,na=False,regex=False)|out.codigo_barras.str.contains(q,na=False,regex=False)|out.grupo.str.upper().str.contains(q,na=False,regex=False)|out.subclasse.str.upper().str.contains(q,na=False,regex=False))
        # Leitor de código de barras entrega o EAN com zeros à esquerda; o código
        # da análise é guardado sem eles.
        if q.isdigit() and q.lstrip("0"):
            m=m|out.codigo_barras.str.contains(q.lstrip("0"),na=False,regex=False)
        out=out[m]
    return out

def kpis(df):
    return {"Valor em estoque":df.valor_estoque.sum(),"Unidades em estoque":df.quantidade_estoque.sum(),
    "Unidades vendidas":df.quantidade_vendida.sum(),"Produtos ativos analisados":len(df),
    "Produtos sem vendas":int(df.produto_sem_venda.sum()),"Produtos em ruptura":int(df.ruptura.sum()),
    "Produtos críticos":int((df.status_estoque=="CRÍTICO").sum()),"Giro médio":df.giro.mean() if len(df) else 0,
    "Margem potencial":(df.margem_unitaria*df.quantidade_estoque).sum(),"Faturamento estimado":df.valor_vendido.sum()}

def pivot_by_store(df, value="quantidade_estoque", ascending=False):
    """Uma métrica (`value`) de cada produto por loja, uma coluna por loja.

    O produto é identificado pelo código de barras, porque a descrição pode
    variar entre lojas; o nome exibido é o mais frequente. Loja sem linha do
    produto em `df` fica vazia (NaN), diferente de zero.
    Colunas de loja na ordem oficial (core.stores) e linhas pelo código de
    barras, do menor para o maior: assim a grade de tamanhos fica em sequência
    (P, M, G, GG). `ascending` é mantido só por compatibilidade.
    Também traz o preço unitário de venda (`preco_min`/`preco_max` e `precos`, por
    loja), com a mesma regra do Excel do estoque: preço do sistema, senão o das vendas.
    Retorna (tabela, lojas, totais por loja).
    """
    if df.empty:
        return df.iloc[0:0], [], {}
    stores = order_stores(df.loja.dropna().unique())
    names = (df.groupby("codigo_barras").descricao
             .agg(lambda s: s.value_counts().index[0]).rename("descricao"))
    groups = df.groupby("codigo_barras")[["grupo", "subclasse"]].first()
    pivot = df.pivot_table(index="codigo_barras", columns="loja", values=value,
                           aggfunc="sum").reindex(columns=stores)
    prices = unit_prices(df)
    table = pd.concat([names, groups, prices, pivot], axis=1).reset_index()
    table["total"] = table[stores].sum(axis=1, min_count=1).fillna(0)
    table = table.sort_values("codigo_barras", key=lambda col: col.map(barcode_sort_key), kind="stable").reset_index(drop=True)
    totals = {store: float(df.loc[df.loja == store, value].sum()) for store in stores}
    return table, stores, totals


def unit_prices(df):
    """Preço unitário de venda de cada código: menor, maior e {loja: preço}."""
    from core.inventory import sale_price  # import tardio: core.inventory usa pandas e catálogo
    has_system = "preco_venda_sistema" in df.columns
    per_code = {}
    for record in df.to_dict("records"):
        price, _origin = sale_price(record, None, has_system)
        if price > 0:
            per_code.setdefault(record["codigo_barras"], {})[str(record.get("loja", ""))] = round(price, 2)
    index = pd.Index(df.codigo_barras.unique(), name="codigo_barras")
    return pd.DataFrame({
        "preco_min": [min(per_code[c].values()) if c in per_code else float("nan") for c in index],
        "preco_max": [max(per_code[c].values()) if c in per_code else float("nan") for c in index],
        "precos": [per_code.get(c, {}) for c in index],
    }, index=index)


def stock_by_store(df):
    """Unidades em estoque de cada produto por loja."""
    return pivot_by_store(df, "quantidade_estoque")


def single_product_labels(df):
    """Com um único produto na análise, KPIs de contagem viram texto legível.

    Retorna {} quando há mais (ou menos) de um produto: aí os números fazem sentido.
    """
    if len(df) != 1:
        return {}
    row = df.iloc[0]
    stock = float(row.quantidade_estoque)
    return {
        "Produtos ativos": "1 PRODUTO",
        "Sem vendas": "SEM VENDAS" if row.quantidade_vendida <= 0 else "COM VENDAS",
        "Em ruptura": "ESTOQUE NEGATIVO" if stock < 0 else "SEM ESTOQUE" if stock == 0 else "COM ESTOQUE",
        "Críticos": str(row.status_estoque),
    }


def top_sold(df,n=10):
    return df.sort_values(
        ["quantidade_vendida", "valor_vendido"],
        ascending=[False, False],
        kind="stable",
    ).head(n)


def stagnant(df,n=10):
    return (
        df[(df.quantidade_estoque > 0) & (df.quantidade_vendida <= 0)]
        .sort_values(["valor_estoque", "quantidade_estoque"], ascending=[False, False], kind="stable")
        .head(n)
    )


def idle_stock(df,n=20):
    """Estoque parado: sem venda no período, ordenado pela maior quantidade em estoque."""
    return (
        df[(df.quantidade_estoque > 0) & (df.quantidade_vendida <= 0)]
        .sort_values(["quantidade_estoque", "valor_estoque"], ascending=[False, False], kind="stable")
        .head(n)
    )


def rupture(df,n=None):
    """Rank stockout products by observed demand, then estimated sales value."""
    x = df[df.ruptura].sort_values(
        ["quantidade_vendida", "valor_vendido"],
        ascending=[False, False],
        kind="stable",
    )
    return x if n is None else x.head(n)


def critical(df,n=None):
    """Rank replenishment attention by severity, coverage risk, and demand."""
    x = df[df.status_estoque.isin(["NEGATIVO", "SEM ESTOQUE", "CRÍTICO", "BAIXO"])].copy()
    status_priority = {"NEGATIVO": 0, "SEM ESTOQUE": 0, "CRÍTICO": 1, "BAIXO": 2}
    x["_prioridade_status"] = x.status_estoque.map(status_priority)
    x = x.sort_values(
        ["_prioridade_status", "risco_ruptura", "cobertura", "quantidade_vendida", "valor_vendido"],
        ascending=[True, False, True, False, False],
        kind="stable",
    ).drop(columns="_prioridade_status")
    return x if n is None else x.head(n)


def sort_products(df):
    """Linhas de produto pelo código de barras (menor → maior) e, no mesmo código, pela ordem das lojas."""
    if df.empty:
        return df
    keys = df.codigo_barras.map(barcode_sort_key)
    stores = df.loja.map(store_sort_key) if "loja" in df else None
    order = sorted(range(len(df)), key=lambda i: (keys.iloc[i], stores.iloc[i] if stores is not None else 0))
    return df.iloc[order]


def product_options(df):
    """Um item por código de barras (nome mais frequente, grupo e subclasse), do menor código para o maior.

    Usado pela seleção de produtos: marcando os tamanhos de um conjunto, eles
    aparecem em sequência (P → GG) porque os códigos da grade são sequenciais.
    """
    if df.empty:
        return []
    names = df.groupby("codigo_barras").descricao.agg(lambda s: s.value_counts().index[0])
    info = df.groupby("codigo_barras")[["grupo", "subclasse"]].first()
    options = [
        {"codigo_barras": code, "descricao": str(names[code]),
         "grupo": str(info.at[code, "grupo"]), "subclasse": str(info.at[code, "subclasse"])}
        for code in names.index
    ]
    return sorted(options, key=lambda o: barcode_sort_key(o["codigo_barras"]))


def match_options(options, query):
    """Filtra pelo texto digitado: todas as palavras no nome/subclasse, ou parte do código."""
    from utils.normalization import normalize_barcode, normalize_text
    words = normalize_text(query).split()
    digits = normalize_barcode(query) if any(ch.isdigit() for ch in str(query)) else ""
    if not words:
        return list(options)
    found = []
    for option in options:
        text = normalize_text(f"{option['descricao']} {option['subclasse']} {option['grupo']} {option['codigo_barras']}")
        if all(word in text for word in words) or (
            digits not in ("", "0") and digits in normalize_barcode(option["codigo_barras"])
        ):
            found.append(option)
    return found

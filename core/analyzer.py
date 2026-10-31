import pandas as pd

# Filter value meaning "do not filter by this field".
ALL = "All"

def filter_analysis(df,loja=ALL,grupo=ALL,subclasse=ALL,busca="",status=ALL):
    out=df
    if loja!=ALL:out=out[out.loja==loja]
    if grupo!=ALL:out=out[out.grupo==grupo]
    if subclasse!=ALL:out=out[out.subclasse==subclasse]
    if status!=ALL:out=out[out.status_estoque==status]
    if busca.strip():
        q=busca.strip().upper()
        m=(out.descricao.str.upper().str.contains(q,na=False,regex=False)|out.codigo_barras.str.contains(q,na=False,regex=False)|out.grupo.str.upper().str.contains(q,na=False,regex=False)|out.subclasse.str.upper().str.contains(q,na=False,regex=False))
        # Barcode scanners send the EAN with leading zeros; the analysis stores
        # codes without them.
        if q.isdigit() and q.lstrip("0"):
            m=m|out.codigo_barras.str.contains(q.lstrip("0"),na=False,regex=False)
        out=out[m]
    return out

def kpis(df):
    return {"Stock value":df.valor_estoque.sum(),"Units in stock":df.quantidade_estoque.sum(),
    "Units sold":df.quantidade_vendida.sum(),"Products analyzed":len(df),
    "Products without sales":int(df.produto_sem_venda.sum()),"Stockout products":int(df.ruptura.sum()),
    "Critical products":int((df.status_estoque=="CRITICAL").sum()),"Average sell-through":df.giro.mean() if len(df) else 0,
    "Potential margin":(df.margem_unitaria*df.quantidade_estoque).sum(),"Estimated revenue":df.valor_vendido.sum()}

def pivot_by_store(df, value="quantidade_estoque", ascending=False):
    """One metric (`value`) for each product per store, one column per store.

    Products are identified by barcode because the description can differ
    between stores; the displayed name is the most frequent one. A store with no
    row for the product in `df` stays empty (NaN), which is different from zero.
    Returns (table, stores, totals per store).
    """
    if df.empty:
        return df.iloc[0:0], [], {}
    stores = sorted(df.loja.dropna().unique(), key=str)
    names = (df.groupby("codigo_barras").descricao
             .agg(lambda s: s.value_counts().index[0]).rename("descricao"))
    groups = df.groupby("codigo_barras")[["grupo", "subclasse"]].first()
    pivot = df.pivot_table(index="codigo_barras", columns="loja", values=value,
                           aggfunc="sum").reindex(columns=stores)
    table = pd.concat([names, groups, pivot], axis=1).reset_index()
    table["total"] = table[stores].sum(axis=1, min_count=1).fillna(0)
    table = table.sort_values(["total", "descricao"], ascending=[ascending, True], kind="stable").reset_index(drop=True)
    totals = {store: float(df.loc[df.loja == store, value].sum()) for store in stores}
    return table, stores, totals


def stock_by_store(df):
    """Units in stock for each product per store."""
    return pivot_by_store(df, "quantidade_estoque")


def single_product_labels(df):
    """With a single product in the analysis, count KPIs become readable text.

    Returns {} when there are more (or fewer) products: then the numbers make sense.
    """
    if len(df) != 1:
        return {}
    row = df.iloc[0]
    stock = float(row.quantidade_estoque)
    return {
        "Active products": "1 PRODUCT",
        "No sales": "NO SALES" if row.quantidade_vendida <= 0 else "HAS SALES",
        "Stockouts": "NEGATIVE STOCK" if stock < 0 else "OUT OF STOCK" if stock == 0 else "IN STOCK",
        "Critical": str(row.status_estoque),
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
    """Idle stock: no sales in the period, ranked by the largest quantity in stock."""
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
    x = df[df.status_estoque.isin(["NEGATIVE", "OUT OF STOCK", "CRITICAL", "LOW"])].copy()
    status_priority = {"NEGATIVE": 0, "OUT OF STOCK": 0, "CRITICAL": 1, "LOW": 2}
    x["_prioridade_status"] = x.status_estoque.map(status_priority)
    x = x.sort_values(
        ["_prioridade_status", "risco_ruptura", "cobertura", "quantidade_vendida", "valor_vendido"],
        ascending=[True, False, True, False, False],
        kind="stable",
    ).drop(columns="_prioridade_status")
    return x if n is None else x.head(n)

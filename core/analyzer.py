import pandas as pd

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
    Retorna (tabela, lojas, totais por loja).
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

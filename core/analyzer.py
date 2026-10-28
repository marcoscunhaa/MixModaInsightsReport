def filter_analysis(df,loja="Todas",grupo="Todos",subclasse="Todas",busca="",status="Todos"):
    out=df
    if loja!="Todas":out=out[out.loja==loja]
    if grupo!="Todos":out=out[out.grupo==grupo]
    if subclasse!="Todas":out=out[out.subclasse==subclasse]
    if status!="Todos":out=out[out.status_estoque==status]
    if busca.strip():
        q=busca.strip().upper()
        m=(out.descricao.str.upper().str.contains(q,na=False,regex=False)|out.codigo_barras.str.contains(q,na=False,regex=False)|out.grupo.str.upper().str.contains(q,na=False,regex=False)|out.subclasse.str.upper().str.contains(q,na=False,regex=False))
        out=out[m]
    return out

def kpis(df):
    return {"Valor em estoque":df.valor_estoque.sum(),"Unidades em estoque":df.quantidade_estoque.sum(),
    "Unidades vendidas":df.quantidade_vendida.sum(),"Produtos ativos analisados":len(df),
    "Produtos sem vendas":int(df.produto_sem_venda.sum()),"Produtos em ruptura":int(df.ruptura.sum()),
    "Produtos críticos":int((df.status_estoque=="CRÍTICO").sum()),"Giro médio":df.giro.mean() if len(df) else 0,
    "Margem potencial":(df.margem_unitaria*df.quantidade_estoque).sum(),"Faturamento estimado":df.valor_vendido.sum()}

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
    x = df[df.status_estoque.isin(["SEM ESTOQUE", "CRÍTICO", "BAIXO"])].copy()
    status_priority = {"SEM ESTOQUE": 0, "CRÍTICO": 1, "BAIXO": 2}
    x["_prioridade_status"] = x.status_estoque.map(status_priority)
    x = x.sort_values(
        ["_prioridade_status", "risco_ruptura", "cobertura", "quantidade_vendida", "valor_vendido"],
        ascending=[True, False, True, False, False],
        kind="stable",
    ).drop(columns="_prioridade_status")
    return x if n is None else x.head(n)

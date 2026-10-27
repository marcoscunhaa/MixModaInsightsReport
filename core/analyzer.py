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

def top_sold(df,n=10): return df.sort_values("quantidade_vendida",ascending=False).head(n)
def stagnant(df,n=10): return df[(df.quantidade_estoque>0)&(df.quantidade_vendida<=0)].sort_values("valor_estoque",ascending=False).head(n)
def critical(df,n=None):
    x=df[df.status_estoque.isin(["SEM ESTOQUE","CRÍTICO","BAIXO"])].sort_values(["risco_ruptura","quantidade_vendida"],ascending=[False,False])
    return x if n is None else x.head(n)

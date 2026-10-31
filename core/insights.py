from utils.formatting import fmt_money, fmt_number
def generate_insights(df):
    if df.empty:return []
    result=[]
    g=df.groupby("grupo",as_index=False).agg(valor_estoque=("valor_estoque","sum"),quantidade_vendida=("quantidade_vendida","sum"))
    r=g.sort_values("valor_estoque",ascending=False).iloc[0]
    result.append({"titulo":"Highest stock concentration","texto":f'{r.grupo} holds {fmt_money(r.valor_estoque)} in stock.','tipo':'grupo','alvo':r.grupo})
    r=g.sort_values("quantidade_vendida",ascending=False).iloc[0]
    result.append({"titulo":"Top-selling group by volume","texto":f'{r.grupo} leads in units sold, with {fmt_number(r.quantidade_vendida,0)}.','tipo':'grupo','alvo':r.grupo})
    p=df[df.quantidade_vendida<=0].sort_values("valor_estoque",ascending=False)
    if len(p):
        r=p.iloc[0]; result.append({"titulo":"Largest idle stock","texto":f'{r.descricao} has {fmt_money(r.valor_estoque)} in stock with no sales in the period.','tipo':'produto','alvo':r.codigo_barras})
    p=df[df.risco_ruptura].sort_values("quantidade_vendida",ascending=False)
    if len(p):
        r=p.iloc[0]; result.append({"titulo":"Stockout risk","texto":f'{r.descricao} sold {r.quantidade_vendida:.0f} units and has only {r.quantidade_estoque:.0f} left in stock.','tipo':'produto','alvo':r.codigo_barras})
    return result

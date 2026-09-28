from utils.formatting import brl, br_number
def generate_insights(df):
    if df.empty:return []
    result=[]
    g=df.groupby("grupo",as_index=False).agg(valor_estoque=("valor_estoque","sum"),quantidade_vendida=("quantidade_vendida","sum"))
    r=g.sort_values("valor_estoque",ascending=False).iloc[0]
    result.append({"titulo":"Maior concentração de estoque","texto":f'{r.grupo} concentra {brl(r.valor_estoque)} em estoque.','tipo':'grupo','alvo':r.grupo})
    r=g.sort_values("quantidade_vendida",ascending=False).iloc[0]
    result.append({"titulo":"Grupo com maior volume vendido","texto":f'{r.grupo} lidera em unidades vendidas, com {br_number(r.quantidade_vendida,0)}.','tipo':'grupo','alvo':r.grupo})
    p=df[df.quantidade_vendida<=0].sort_values("valor_estoque",ascending=False)
    if len(p):
        r=p.iloc[0]; result.append({"titulo":"Maior estoque parado","texto":f'{r.descricao} possui {brl(r.valor_estoque)} sem vendas no período.','tipo':'produto','alvo':r.codigo_barras})
    p=df[df.risco_ruptura].sort_values("quantidade_vendida",ascending=False)
    if len(p):
        r=p.iloc[0]; result.append({"titulo":"Risco de ruptura","texto":f'{r.descricao} vendeu {r.quantidade_vendida:.0f} un. e está com {r.quantidade_estoque:.0f} em estoque.','tipo':'produto','alvo':r.codigo_barras})
    return result

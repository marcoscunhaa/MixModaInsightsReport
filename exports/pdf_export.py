from utils.formatting import brl, br_number
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
def export_dashboard_pdf(path,df,period,loja,audit):
    doc=SimpleDocTemplate(path,pagesize=landscape(A4),rightMargin=12*mm,leftMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm); st=getSampleStyleSheet()
    story=[Paragraph("MIX MODA INSIGHTS",st["Title"]),Paragraph(f"Período: {period[0].strftime('%d/%m/%Y')} a {period[1].strftime('%d/%m/%Y')} • Loja: {loja}",st["Normal"]),Spacer(1,8)]
    k=[["Valor estoque",brl(df.valor_estoque.sum()),"Unidades estoque",br_number(df.quantidade_estoque.sum(),0),"Unidades vendidas",br_number(df.quantidade_vendida.sum(),0)],["Sem vendas",str(int(df.produto_sem_venda.sum())),"Rupturas",str(int(df.ruptura.sum())),"Críticos",str(int((df.status_estoque=="CRÍTICO").sum()))]]
    t=Table(k,colWidths=[35*mm,40*mm]*3); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.whitesmoke),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("PADDING",(0,0),(-1,-1),6)])); story += [t,Spacer(1,12),Paragraph("Produtos mais vendidos",st["Heading2"])]
    top=df.sort_values("quantidade_vendida",ascending=False).head(25); data=[["Produto","Grupo","Subclasse","Vendidas","Estoque","Valor estoque"]]
    for _,r in top.iterrows():data.append([str(r.descricao)[:48],str(r.grupo)[:28],str(r.subclasse)[:25],f'{r.quantidade_vendida:.0f}',f'{r.quantidade_estoque:.0f}',brl(r.valor_estoque)])
    tt=Table(data,repeatRows=1,colWidths=[65*mm,42*mm,40*mm,22*mm,22*mm,32*mm]); tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#233b8f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8fb")])]))
    story.append(tt); story.append(PageBreak()); story.append(Paragraph("Qualidade dos dados",st["Heading2"]))
    for k,v in audit.items():story.append(Paragraph(f"{k}: {v}",st["Normal"]))
    story.append(Spacer(1,10)); story.append(Paragraph("Produtos críticos",st["Heading2"])); crit=df[df.status_estoque.isin(["SEM ESTOQUE","CRÍTICO","BAIXO"])].sort_values("quantidade_vendida",ascending=False).head(40)
    data=[["Produto","Grupo","Estoque","Vendas","Status"]]
    for _,r in crit.iterrows():data.append([str(r.descricao)[:60],str(r.grupo)[:30],f'{r.quantidade_estoque:.0f}',f'{r.quantidade_vendida:.0f}',str(r.status_estoque)])
    story.append(Table(data,repeatRows=1,colWidths=[90*mm,55*mm,25*mm,25*mm,35*mm],style=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#233b8f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),.25,colors.lightgrey)])))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont("Helvetica",7); canvas.drawString(12*mm,7*mm,"Mix Moda Insights"); canvas.drawRightString(285*mm,7*mm,f"Página {doc.page}"); canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)

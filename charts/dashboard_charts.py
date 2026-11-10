from utils.formatting import brl, br_number
from matplotlib.figure import Figure
import numpy as np

NAVY="#14284B"; BLUE="#2854D9"; CYAN="#16B8C8"; TEAL="#0F9D8A"; GOLD="#F3B63F"; PINK="#E85D8A"; LIGHT="#EAF0FF"

# Tamanho de cada gráfico (polegadas a 100 dpi): define a altura inicial do canvas.
SIZES={"grupo_valor_3d":(7.0,3.75),"grupo_pizza":(7.0,4.0),"vendas_3d":(7.4,4.25),"rotacao":(7.0,3.75),
       "status":(6.3,3.25),"top":(6.3,3.5),"estoque_x_vendas":(6.3,3.5)}
_DEFAULT_MARGINS=dict(left=.125,right=.9,top=.88,bottom=.11)


def make_chart(kind,df):
    """Cria o canvas do gráfico `kind`. Para atualizar depois, use `update_chart` (não cria outro)."""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # Qt só aqui: draw_chart roda sem Qt
    fig=Figure(figsize=SIZES.get(kind,(6.3,3.5)),dpi=100)
    canvas=FigureCanvas(fig)
    draw_chart(fig,kind,df)
    return canvas


def update_chart(canvas,kind,df):
    """Redesenha o mesmo canvas com outros dados: sem criar figura nova (economiza memória e tempo)."""
    draw_chart(canvas.figure,kind,df)
    canvas.draw_idle()


def _base(fig, title, w=6.3, h=3.35):
    # Limpa a figura (reaproveitada entre atualizações) e volta às margens padrão.
    fig.clear(); fig.subplots_adjust(**_DEFAULT_MARGINS); fig.patch.set_facecolor("#FFFFFF")
    ax=fig.add_subplot(111); ax.set_facecolor("#FFFFFF")
    ax.set_title(title,loc="left",fontsize=12,fontweight="bold",color=NAVY,pad=12)
    for s in ax.spines.values(): s.set_visible(False)
    ax.grid(axis="y",alpha=.08); ax.tick_params(colors="#718097",labelsize=8)
    return fig,ax

def draw_chart(fig,kind,df):
    """Desenha o gráfico `kind` na figura `fig` (apaga o que havia nela)."""
    if df.empty:
        fig,ax=_base(fig,"Sem dados para exibir"); ax.axis("off"); return fig
    if kind=="grupo_valor_3d":
        # Troca do 3D por ranking horizontal: mais legível, sem perspectiva
        # distorcendo a comparação entre grupos e sem cortar os nomes.
        fig,ax=_base(fig,"Concentração de estoque por grupo",7.0,3.75)
        x=df.groupby("grupo").valor_estoque.sum().sort_values(ascending=True).tail(8)
        labels=[str(v) for v in x.index]
        y=np.arange(len(x))
        bars=ax.barh(y,x.values,height=.58,color="#9B5DE5",alpha=.96)
        ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=8,color="#50627E")
        ax.set_xlabel("Valor em estoque",fontsize=8,color="#7A8498")
        ax.tick_params(axis="x",labelsize=8)
        ax.grid(axis="x",alpha=.10); ax.grid(axis="y",visible=False)
        ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color("#DCE5F1")
        for bar,val in zip(bars,x.values):
            ax.text(val,max(bar.get_y()+bar.get_height()/2,0),brl(val,0),va="center",ha="left",fontsize=7.5,fontweight="bold",color=NAVY)
        fig.subplots_adjust(left=.31,right=.96,top=.84,bottom=.18)
        return fig
    if kind=="grupo_pizza":
        fig,ax=_base(fig,"Grupos com maior volume de vendas",7.0,4.0); x=df.groupby("grupo").quantidade_vendida.sum().sort_values(ascending=False); x=x[x>0].head(7)
        if len(x):
            vals=x.values; labels=[str(i) for i in x.index]
            # Cores fixas por grupo: Cosméticos sempre roxo e Vestuário Fem. Adul. sempre azul.
            # Paleta determinística: Cosméticos e Vestuário Fem. Adul. têm cores fixas.
            # Cada outro grupo recebe uma cor diferente dentro do gráfico, sem reutilizar
            # roxo/azul e sem repetir a mesma cor entre os grupos exibidos.
            palette=[
                "#E85D8A", "#16B8C8", "#F3B63F", "#FF7A59",
                "#00A88F", "#36A269", "#D94D9A", "#8B6FE8",
                "#19A9C7", "#F06A9B", "#4B8EF7", "#B36BFF"
            ]
            def normalized_group(name):
                import unicodedata
                return "".join(c for c in unicodedata.normalize("NFD",str(name).upper()) if unicodedata.category(c)!="Mn")
            fixed_colors={}
            other_idx=0
            for name in labels:
                key=normalized_group(name)
                if "COSMET" in key:
                    fixed_colors[name]="#7C3AED"
                elif "VESTUARIO FEM ADUL" in key or ("VESTUARIO" in key and "FEM" in key and "ADUL" in key):
                    fixed_colors[name]="#2C9FD6"
                elif "VESTUARIO MASC ADUL" in key or ("VESTUARIO" in key and "MASC" in key and "ADUL" in key):
                    # Verde-esmeralda para separar visualmente do azul feminino.
                    fixed_colors[name]="#00A88F"
                else:
                    # Escolhe a próxima cor ainda não usada.
                    fixed_colors[name]=palette[other_idx % len(palette)]
                    other_idx += 1
            def group_color(name, idx):
                return fixed_colors[name]
            colors=[group_color(name,i) for i,name in enumerate(labels)]
            wedges,_,autotexts=ax.pie(vals,labels=None,startangle=90,colors=colors,wedgeprops=dict(width=.42,edgecolor="white",linewidth=2),autopct=lambda p:f"{p:.0f}%" if p>=7 else "",pctdistance=.72)
            for txt in autotexts:
                txt.set_fontsize(9); txt.set_fontweight("bold"); txt.set_color(NAVY)
            legend_labels=[f"{name[:24]}  •  {br_number(val,0)} un." for name,val in zip(labels,vals)]
            leg=ax.legend(wedges,legend_labels,loc="upper center",bbox_to_anchor=(.5,-.04),frameon=False,fontsize=7.5,ncol=2,columnspacing=1.2,handlelength=1.2)
            for t in leg.get_texts(): t.set_color(NAVY)
            ax.axis("equal"); fig.subplots_adjust(left=.03,right=.97,top=.84,bottom=.30)
        return fig
    if kind=="vendas_3d":
        # Barras verticais simples, vinho, com bastante respiro entre barras e legenda.
        fig,ax=_base(fig,"Volume vendido por grupo",7.4,4.25)
        ax.spines["bottom"].set_visible(True)  # este gráfico mostra a linha de base
        x=df.groupby("grupo").quantidade_vendida.sum().sort_values(ascending=False).head(8)
        labels=[str(v) for v in x.index]; vals=x.values.astype(float); xpos=np.arange(len(vals))
        wine="#E85D8A"
        bars=ax.bar(xpos,vals,width=.48,color=wine,alpha=.95)
        ax.set_xticks(xpos); ax.set_xticklabels([lab[:18] for lab in labels],rotation=-28,ha="left",fontsize=7.5,color="#50627E")
        ax.set_ylabel("Unidades",fontsize=8,color="#718097")
        ax.tick_params(axis="y",labelsize=7.5,colors="#718097")
        ax.grid(axis="y",alpha=.10); ax.grid(axis="x",visible=False)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color("#DCE5F1")
        for bar,val in zip(bars,vals):
            ax.text(bar.get_x()+bar.get_width()/2,val*1.015,f"{br_number(val,0)}",ha="center",va="bottom",fontsize=7.5,fontweight="bold",color=NAVY)
        fig.subplots_adjust(left=.08,right=.97,top=.84,bottom=.36)
        return fig
    if kind=="rotacao":
        fig,ax=_base(fig,"Giro médio do período por grupo",7.0,3.75)
        x=df.groupby("grupo").giro.mean().sort_values(ascending=True).tail(10)
        labels=[str(i) for i in x.index]
        y=np.arange(len(x))
        bars=ax.barh(y,x.values,height=.56,color=CYAN,alpha=.94)
        ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=8,color="#50627E")
        ax.set_xlabel("Sell-through do período (%)",fontsize=8,color="#7A8498")
        ax.tick_params(axis="x",labelsize=8)
        ax.grid(axis="x",alpha=.10); ax.grid(axis="y",visible=False)
        ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color("#DCE5F1")
        for bar,val in zip(bars,x.values):
            ax.text(val,max(bar.get_y()+bar.get_height()/2,0),f"{val:.1f}%",va="center",ha="left",fontsize=7.5,fontweight="bold",color=NAVY)
        fig.subplots_adjust(left=.34,right=.96,top=.84,bottom=.18)
        return fig
    if kind=="status":
        # Saúde do estoque em pizza: distribuição dos produtos por status.
        fig,ax=_base(fig,"Saúde do estoque",6.3,3.25)
        x=df.status_estoque.value_counts()
        colors_map={"NORMAL":TEAL,"CRÍTICO":PINK,"BAIXO":GOLD,"SEM ESTOQUE":"#D9284B","NEGATIVO":"#7F1D1D","EXCESSO":"#7C6FE6","SEM VENDA":BLUE}
        colors=[colors_map.get(str(k).upper(),"#97A2B6") for k in x.index]
        vals=x.values
        wedges,_,autotexts=ax.pie(vals,labels=None,startangle=90,colors=colors,
            wedgeprops=dict(width=.48,edgecolor="white",linewidth=2),
            autopct=lambda p:f"{p:.0f}%" if p>=7 else "",pctdistance=.72)
        for txt in autotexts:
            txt.set_fontsize(8); txt.set_fontweight("bold"); txt.set_color(NAVY)
        legend_labels=[f"{str(name).title()}  •  {br_number(val,0)}" for name,val in zip(x.index,vals)]
        leg=ax.legend(wedges,legend_labels,loc="center left",bbox_to_anchor=(.98,.5),
            frameon=False,fontsize=7.5,handlelength=1.1,labelspacing=.75)
        for t in leg.get_texts(): t.set_color(NAVY)
        ax.text(0,0,"ESTOQUE",ha="center",va="center",fontsize=8,fontweight="bold",color="#718097")
        ax.axis("equal")
        fig.subplots_adjust(left=.02,right=.72,top=.86,bottom=.05)
        return fig
    if kind=="top":
        fig,ax=_base(fig,"Top produtos vendidos",6.3,3.5); x=df.sort_values("quantidade_vendida").tail(8); ax.barh([str(v)[:28] for v in x.descricao],x.quantidade_vendida,color=BLUE); return fig
    fig,ax=_base(fig,"Estoque × vendas",6.3,3.5); x=df.sample(min(len(df),500),random_state=1); ax.scatter(x.quantidade_vendida,x.quantidade_estoque,s=28,alpha=.55,color=BLUE,edgecolors="white",linewidths=.4); ax.set_xlabel("Vendas",fontsize=8); ax.set_ylabel("Estoque",fontsize=8); return fig

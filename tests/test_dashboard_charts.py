"""Gráficos do dashboard: a mesma figura é redesenhada, sem acumular eixos nem memória."""
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from charts.dashboard_charts import SIZES, draw_chart

KINDS = ("grupo_valor_3d", "grupo_pizza", "vendas_3d", "rotacao", "status", "estoque_x_vendas")


def frame(n=40):
    return pd.DataFrame({
        "grupo": [f"GRUPO {i % 5}" for i in range(n)],
        "descricao": [f"PRODUTO {i}" for i in range(n)],
        "valor_estoque": [float(i) for i in range(n)],
        "quantidade_vendida": [i % 4 for i in range(n)],
        "quantidade_estoque": [i % 7 - 1 for i in range(n)],
        "giro": [float(i % 9) for i in range(n)],
        "status_estoque": ["NORMAL", "CRÍTICO", "BAIXO", "SEM ESTOQUE"][0:1] * n,
    })


def test_every_chart_redraws_on_the_same_figure():
    for kind in KINDS:
        fig = Figure(figsize=SIZES[kind])
        FigureCanvasAgg(fig)
        for data in (frame(), frame(12), frame().iloc[0:0], frame()):
            assert draw_chart(fig, kind, data) is fig
            assert len(fig.axes) == 1  # limpou antes de desenhar: não empilha eixos
            fig.canvas.draw()


def test_empty_data_resets_margins_after_a_custom_layout():
    fig = Figure()
    FigureCanvasAgg(fig)
    draw_chart(fig, "grupo_pizza", frame())
    draw_chart(fig, "grupo_pizza", frame().iloc[0:0])
    assert fig.subplotpars.bottom == 0.11 and fig.axes[0].get_title(loc="left") == "Sem dados para exibir"

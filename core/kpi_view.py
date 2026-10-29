"""O que os cards de KPI e as pílulas de status do dashboard mostram.

Fica fora da interface para poder ser testado: cada KPI tem nome claro, valor,
uma frase explicando o número e um tom (bom, alerta, ruim) que define a cor.
"""
from core.analyzer import kpis, rupture, single_product_labels
from core.models import AnalysisConfig
from utils.formatting import brl, br_number

CRITICAL = AnalysisConfig.estoque_critico
LOW = AnalysisConfig.estoque_baixo
EXCESS = AnalysisConfig.excesso_cobertura

# (valor do status, rótulo, emoji, cor, explicação)
STATUS_OPTIONS = [
    ("Todos os status", "Todos", "🗂️", "#2854D9", "Todos os produtos da seleção."),
    ("NEGATIVO", "Negativo", "🔻", "#7F1D1D", "Estoque abaixo de zero: venda registrada sem entrada no sistema."),
    ("SEM ESTOQUE", "Sem estoque", "⛔", "#D9284B", "Estoque igual a zero."),
    ("CRÍTICO", "Crítico", "⚠️", "#E8590C", f"Até {br_number(CRITICAL, 0)} unidade em estoque."),
    ("BAIXO", "Baixo", "🟡", "#B77900", f"Até {br_number(LOW, 0)} unidades em estoque."),
    ("SEM VENDA", "Sem venda", "💤", "#5F6D82", "Tem estoque, mas não vendeu nada no período."),
    ("EXCESSO", "Excesso", "📦", "#4C5BD4",
     f"Estoque para {br_number(EXCESS, 0)} vezes ou mais as vendas do período."),
    ("NORMAL", "Normal", "✅", "#087F6A", "Estoque saudável para o ritmo de vendas."),
]


def status_counts(df):
    counts = df.status_estoque.value_counts().to_dict() if len(df) else {}
    counts["Todos os status"] = len(df)
    return counts


def _pct(part, whole):
    return f"{part / whole * 100:.0f}%".replace(".", ",") if whole else "0%"


def kpi_cards(d):
    """Lista de cards na ordem de exibição (duas linhas de cinco)."""
    kp = kpis(d)
    total = len(d)
    in_stock = int((d.quantidade_estoque > 0).sum()) if total else 0
    sold = int((d.quantidade_vendida > 0).sum()) if total else 0
    stores = d.loja.dropna().unique() if total and "loja" in d else []
    if len(stores) > 1:
        units_hint = " · ".join(
            f"{store} {br_number(d.loc[d.loja == store, 'quantidade_estoque'].sum(), 0)}"
            for store in sorted(stores, key=str)
        )
    else:
        units_hint = f"em {br_number(in_stock, 0)} produtos com estoque"
    unsold = int(kp["Produtos sem vendas"])
    rupture = int(kp["Produtos em ruptura"])
    critical = int(kp["Produtos críticos"])

    def card(key, label, emoji, accent, value, hint, tone="neutral", clickable=False):
        return {"key": key, "label": label, "emoji": emoji, "accent": accent, "value": value,
                "hint": hint, "tone": tone, "clickable": clickable}

    cards = [
        # Linha 1: dinheiro e volume
        card("Valor em estoque", "Valor em estoque", "💰", "#2854D9", brl(kp["Valor em estoque"]),
             f"custo das {br_number(kp['Unidades em estoque'], 0)} un. em estoque", clickable=True),
        card("Faturamento estimado", "Faturamento", "💵", "#0F9D8A", brl(kp["Faturamento estimado"]),
             "soma das vendas do período"),
        card("Margem potencial", "Margem potencial", "📈", "#0F9D8A", brl(kp["Margem potencial"]),
             "lucro se o estoque atual for vendido"),
        card("Unidades em estoque", "Unidades em estoque", "📦", "#16B8C8", br_number(kp["Unidades em estoque"], 0),
             units_hint, clickable=True),
        card("Unidades vendidas", "Unidades vendidas", "🛒", "#16B8C8", br_number(kp["Unidades vendidas"], 0),
             f"{br_number(sold, 0)} produtos venderam no período", clickable=True),
        # Linha 2: saúde do estoque
        card("Produtos ativos", "Produtos analisados", "🏷️", "#7C6FE6", br_number(total, 0),
             "na seleção atual"),
        card("Sem vendas", "Sem vendas", "💤", "#E85D8A", br_number(unsold, 0),
             f"{_pct(unsold, total)} dos produtos não venderam" if unsold else "✓ todos venderam no período",
             "warn" if unsold else "good", clickable=True),
        card("Em ruptura", "Em ruptura", "🚫", "#D9284B", br_number(rupture, 0),
             "venderam e estão sem estoque" if rupture else "✓ nenhum produto em ruptura",
             "bad" if rupture else "good", clickable=True),
        card("Críticos", "Estoque crítico", "⚠️", "#E8590C", br_number(critical, 0),
             f"com até {br_number(CRITICAL, 0)} un. em estoque" if critical else "✓ nenhum produto crítico",
             "bad" if critical else "good", clickable=True),
        card("Giro médio do período", "Giro do período", "🔄", "#2854D9", f"{kp['Giro médio']:.1f}%".replace(".", ","),
             "vendas ÷ (vendas + estoque)"),
    ]

    # Produto isolado: contagens 0/1 confundem, então esses KPIs viram texto.
    labels = single_product_labels(d)
    if labels:
        row = d.iloc[0]
        hints = {
            "Produtos ativos": "produto isolado pelos filtros",
            "Sem vendas": "no período selecionado",
            "Em ruptura": "situação do estoque deste produto",
            "Críticos": "status do estoque deste produto",
        }
        tones = {
            "Produtos ativos": "neutral",
            "Sem vendas": "bad" if row.quantidade_vendida <= 0 else "good",
            "Em ruptura": "good" if row.quantidade_estoque > 0 else "bad",
            "Críticos": ("good" if row.status_estoque in ("NORMAL", "EXCESSO") else
                         "bad" if row.status_estoque in ("NEGATIVO", "SEM ESTOQUE", "CRÍTICO") else "warn"),
        }
        for item in cards:
            if item["key"] in labels:
                item.update(value=labels[item["key"]], hint=hints[item["key"]], tone=tones[item["key"]])
    return cards


def store_list_view(key, d, status="Todos os status"):
    """O que a lista "por loja" de cada KPI mostra.

    Devolve {title, emoji, rows, value, kind, ascending, note} ou None se o KPI não
    tem lista. `kind`: "money" (R$), "stock" (destaca zerado/negativo) ou "units".
    """
    zero_or_negative = status in ("SEM ESTOQUE", "NEGATIVO")
    views = {
        "Valor em estoque": (
            dict(title=f"Valor em estoque • {'Negativos' if status == 'NEGATIVO' else 'Sem estoque'}",
                 emoji="💰", rows=d, value="quantidade_estoque", kind="stock", ascending=True,
                 note="Unidades em estoque de cada loja (zerados e negativos).")
            if zero_or_negative else
            dict(title="Valor em estoque por loja", emoji="💰", rows=d[d.quantidade_estoque > 0],
                 value="valor_estoque", kind="money", ascending=False,
                 note="Custo do estoque de cada produto em cada loja.")
        ),
        "Unidades em estoque": dict(
            title="Estoque por loja", emoji="📦", rows=d, value="quantidade_estoque", kind="stock",
            ascending=False, note="Unidades em estoque de cada produto em cada loja."),
        "Unidades vendidas": dict(
            title="Vendas por loja", emoji="🛒", rows=d[d.quantidade_vendida > 0], value="quantidade_vendida",
            kind="units", ascending=False, note="Unidades vendidas no período em cada loja."),
        "Sem vendas": dict(
            title="Sem vendas • estoque parado por loja", emoji="💤", rows=d[d.produto_sem_venda],
            value="quantidade_estoque", kind="stock", ascending=False,
            note="Unidades em estoque dos produtos que não venderam nada no período naquela loja."),
        "Em ruptura": dict(
            title="Em ruptura • vendas por loja", emoji="🚫", rows=rupture(d), value="quantidade_vendida",
            kind="units", ascending=False,
            note="Quanto cada loja vendeu do produto no período antes de ficar sem estoque."),
        "Críticos": dict(
            title="Estoque crítico por loja", emoji="⚠️", rows=d[d.status_estoque == "CRÍTICO"],
            value="quantidade_estoque", kind="stock", ascending=True,
            note=f"Unidades em estoque dos produtos com até {br_number(CRITICAL, 0)} un. naquela loja."),
    }
    return views.get(key)

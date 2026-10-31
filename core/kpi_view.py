"""What the dashboard's KPI cards and status pills show.

Kept outside the UI so it can be tested: each KPI has a clear name, a value,
a sentence explaining the number and a tone (good, warn, bad) that sets the color.
"""
from core.analyzer import kpis, rupture, single_product_labels
from core.models import AnalysisConfig
from utils.formatting import fmt_money, fmt_number

CRITICAL = AnalysisConfig.estoque_critico
LOW = AnalysisConfig.estoque_baixo
EXCESS = AnalysisConfig.excesso_cobertura

ALL_STATUSES = "All statuses"

# (status value, label, emoji, color, explanation)
STATUS_OPTIONS = [
    (ALL_STATUSES, "All", "🗂️", "#2854D9", "Every product in the selection."),
    ("NEGATIVE", "Negative", "🔻", "#7F1D1D", "Stock below zero: a sale was recorded without a stock receipt."),
    ("OUT OF STOCK", "Out of stock", "⛔", "#D9284B", "Stock equal to zero."),
    ("CRITICAL", "Critical", "⚠️", "#E8590C", f"Up to {fmt_number(CRITICAL, 0)} unit in stock."),
    ("LOW", "Low", "🟡", "#B77900", f"Up to {fmt_number(LOW, 0)} units in stock."),
    ("NO SALES", "No sales", "💤", "#5F6D82", "Has stock, but sold nothing in the period."),
    ("EXCESS", "Excess", "📦", "#4C5BD4",
     f"Stock covers {fmt_number(EXCESS, 0)} times the period's sales or more."),
    ("NORMAL", "Normal", "✅", "#087F6A", "Healthy stock for the sales pace."),
]


def status_counts(df):
    counts = df.status_estoque.value_counts().to_dict() if len(df) else {}
    counts[ALL_STATUSES] = len(df)
    return counts


def _pct(part, whole):
    return f"{part / whole * 100:.0f}%" if whole else "0%"


def kpi_cards(d):
    """Cards in display order (two rows of five)."""
    kp = kpis(d)
    total = len(d)
    in_stock = int((d.quantidade_estoque > 0).sum()) if total else 0
    sold = int((d.quantidade_vendida > 0).sum()) if total else 0
    stores = d.loja.dropna().unique() if total and "loja" in d else []
    if len(stores) > 1:
        units_hint = " · ".join(
            f"{store} {fmt_number(d.loc[d.loja == store, 'quantidade_estoque'].sum(), 0)}"
            for store in sorted(stores, key=str)
        )
    else:
        units_hint = f"across {fmt_number(in_stock, 0)} products in stock"
    unsold = int(kp["Products without sales"])
    rupture = int(kp["Stockout products"])
    critical = int(kp["Critical products"])

    def card(key, label, emoji, accent, value, hint, tone="neutral", clickable=False):
        return {"key": key, "label": label, "emoji": emoji, "accent": accent, "value": value,
                "hint": hint, "tone": tone, "clickable": clickable}

    cards = [
        # Row 1: money and volume
        card("Stock value", "Stock value", "💰", "#2854D9", fmt_money(kp["Stock value"]),
             f"cost of the {fmt_number(kp['Units in stock'], 0)} units in stock", clickable=True),
        card("Estimated revenue", "Revenue", "💵", "#0F9D8A", fmt_money(kp["Estimated revenue"]),
             "total sales in the period", clickable=True),
        card("Potential margin", "Potential margin", "📈", "#0F9D8A", fmt_money(kp["Potential margin"]),
             "profit if the current stock is sold"),
        card("Units in stock", "Units in stock", "📦", "#16B8C8", fmt_number(kp["Units in stock"], 0),
             units_hint, clickable=True),
        card("Units sold", "Units sold", "🛒", "#16B8C8", fmt_number(kp["Units sold"], 0),
             f"{fmt_number(sold, 0)} products sold in the period", clickable=True),
        # Row 2: stock health
        card("Active products", "Products analyzed", "🏷️", "#7C6FE6", fmt_number(total, 0),
             "in the current selection"),
        card("No sales", "No sales", "💤", "#E85D8A", fmt_number(unsold, 0),
             f"{_pct(unsold, total)} of products did not sell" if unsold else "✓ every product sold in the period",
             "warn" if unsold else "good", clickable=True),
        card("Stockouts", "Stockouts", "🚫", "#D9284B", fmt_number(rupture, 0),
             "sold and are now out of stock" if rupture else "✓ no products out of stock",
             "bad" if rupture else "good", clickable=True),
        card("Critical", "Critical stock", "⚠️", "#E8590C", fmt_number(critical, 0),
             f"with up to {fmt_number(CRITICAL, 0)} unit in stock" if critical else "✓ no critical products",
             "bad" if critical else "good", clickable=True),
        card("Period sell-through", "Sell-through", "🔄", "#2854D9", f"{kp['Average sell-through']:.1f}%",
             "sales ÷ (sales + stock)"),
    ]

    # Single product: 0/1 counts are confusing, so these KPIs become text.
    labels = single_product_labels(d)
    if labels:
        row = d.iloc[0]
        hints = {
            "Active products": "product isolated by the filters",
            "No sales": "in the selected period",
            "Stockouts": "stock situation of this product",
            "Critical": "stock status of this product",
        }
        tones = {
            "Active products": "neutral",
            "No sales": "bad" if row.quantidade_vendida <= 0 else "good",
            "Stockouts": "good" if row.quantidade_estoque > 0 else "bad",
            "Critical": ("good" if row.status_estoque in ("NORMAL", "EXCESS") else
                         "bad" if row.status_estoque in ("NEGATIVE", "OUT OF STOCK", "CRITICAL") else "warn"),
        }
        for item in cards:
            if item["key"] in labels:
                item.update(value=labels[item["key"]], hint=hints[item["key"]], tone=tones[item["key"]])
    return cards


def store_list_view(key, d, status=ALL_STATUSES):
    """What each KPI's "by store" list shows.

    Returns {title, emoji, rows, value, kind, ascending, note}, or None if the KPI
    has no list. `kind`: "money", "stock" (highlights zero/negative) or "units".
    """
    zero_or_negative = status in ("OUT OF STOCK", "NEGATIVE")
    views = {
        "Stock value": (
            dict(title=f"Stock value • {'Negative' if status == 'NEGATIVE' else 'Out of stock'}",
                 emoji="💰", rows=d, value="quantidade_estoque", kind="stock", ascending=True,
                 note="Units in stock at each store (zero and negative).")
            if zero_or_negative else
            dict(title="Stock value by store", emoji="💰", rows=d[d.quantidade_estoque > 0],
                 value="valor_estoque", kind="money", ascending=False,
                 note="Stock cost of each product at each store.")
        ),
        "Estimated revenue": dict(
            title="Revenue by store", emoji="💵", rows=d[d.valor_vendido > 0], value="valor_vendido",
            kind="money", ascending=False, note="Sales value of each product in the period at each store (column G)."),
        "Units in stock": dict(
            title="Stock by store", emoji="📦", rows=d, value="quantidade_estoque", kind="stock",
            ascending=False, note="Units in stock of each product at each store."),
        "Units sold": dict(
            title="Sales by store", emoji="🛒", rows=d[d.quantidade_vendida > 0], value="quantidade_vendida",
            kind="units", ascending=False, note="Units sold in the period at each store."),
        "No sales": dict(
            title="No sales • idle stock by store", emoji="💤", rows=d[d.produto_sem_venda],
            value="quantidade_estoque", kind="stock", ascending=False,
            note="Units in stock of products that sold nothing in the period at that store."),
        "Stockouts": dict(
            title="Stockouts • sales by store", emoji="🚫", rows=rupture(d), value="quantidade_vendida",
            kind="units", ascending=False,
            note="How much each store sold of the product in the period before running out."),
        "Critical": dict(
            title="Critical stock by store", emoji="⚠️", rows=d[d.status_estoque == "CRITICAL"],
            value="quantidade_estoque", kind="stock", ascending=True,
            note=f"Units in stock of products with up to {fmt_number(CRITICAL, 0)} unit at that store."),
    }
    return views.get(key)

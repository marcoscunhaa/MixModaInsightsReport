"""Executive PDF report for Mix Moda stock and sales analyses."""

from math import isfinite
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from core.analyzer import critical as ranked_critical, idle_stock, top_sold

from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils.formatting import fmt_money, fmt_number


NAVY = colors.HexColor("#14284B")
BLUE = colors.HexColor("#2854D9")
TEAL = colors.HexColor("#0F9D8A")
CYAN = colors.HexColor("#16AFC0")
GOLD = colors.HexColor("#E6A92E")
PINK = colors.HexColor("#D94F70")
INK = colors.HexColor("#1D2D47")
MUTED = colors.HexColor("#718097")
PALE = colors.HexColor("#F3F6FB")
LINE = colors.HexColor("#E1E7F0")
WHITE = colors.white


def _stylebook():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=21, leading=24, textColor=WHITE, alignment=TA_LEFT, spaceAfter=0,
        ),
        "brand": ParagraphStyle(
            "ReportBrand", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=11, textColor=colors.HexColor("#B9C9E7"),
            tracking=1.2, spaceAfter=5,
        ),
        "meta": ParagraphStyle(
            "ReportMeta", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=12, textColor=colors.HexColor("#D8E1F1"),
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "ReportSection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=NAVY, spaceBefore=2, spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "ReportSubsection", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, leading=12, textColor=NAVY,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=11, textColor=INK,
        ),
        "muted": ParagraphStyle(
            "ReportMuted", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.5, leading=10, textColor=MUTED,
        ),
        "legend": ParagraphStyle(
            "ReportLegend", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.1, leading=9, textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "ReportTableHead", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=7.2, leading=9, textColor=WHITE,
        ),
        "table": ParagraphStyle(
            "ReportTable", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.2, leading=9, textColor=INK,
        ),
        "table_bold": ParagraphStyle(
            "ReportTableBold", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=7.2, leading=9, textColor=INK,
        ),
        "callout_title": ParagraphStyle(
            "ReportCalloutTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=7, leading=9, textColor=MUTED,
        ),
        "callout_value": ParagraphStyle(
            "ReportCalloutValue", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, leading=12, textColor=NAVY,
        ),
    }


class HorizontalBars(Flowable):
    """Compact vector bar chart that stays crisp in print and PDF viewers."""

    def __init__(self, title, rows, value_formatter, accent=BLUE, width=360, max_rows=6):
        super().__init__()
        self.title = title
        self.rows = list(rows[:max_rows])
        self.value_formatter = value_formatter
        self.accent = accent
        self.width = width
        self.height = 31 + max(1, len(self.rows)) * 19

    def wrap(self, available_width, available_height):
        self.width = min(self.width, available_width)
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(0, self.height - 10, self.title)
        if not self.rows:
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7.5)
            c.drawString(0, self.height - 29, "No data to display")
            return

        max_value = max(float(value) for _, value in self.rows)
        max_value = max(max_value, 1.0)
        label_width = min(116, self.width * 0.34)
        value_width = min(68, self.width * 0.2)
        bar_x = label_width + 7
        bar_width = max(45, self.width - bar_x - value_width - 8)
        for index, (label, value) in enumerate(self.rows):
            y = self.height - 31 - (index + 1) * 19 + 5
            label = str(label)
            if len(label) > 24:
                label = label[:21].rstrip() + "..."
            c.setFillColor(INK)
            c.setFont("Helvetica", 7)
            c.drawString(0, y + 2, label)
            c.setFillColor(PALE)
            c.roundRect(bar_x, y, bar_width, 9, 4, fill=1, stroke=0)
            amount = max(0.0, float(value))
            filled = max(2, bar_width * amount / max_value) if amount else 0
            if filled:
                c.setFillColor(self.accent)
                c.roundRect(bar_x, y, filled, 9, 4, fill=1, stroke=0)
            c.setFillColor(MUTED)
            c.setFont("Helvetica-Bold", 6.7)
            c.drawRightString(self.width, y + 1, self.value_formatter(value))


def _paragraph(text, style, markup=False):
    content = str(text) if markup else escape(str(text))
    return Paragraph(content, style)


def _table(data, widths, header=True, font_size=7.2, paddings=5):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), paddings),
        ("RIGHTPADDING", (0, 0), (-1, -1), paddings),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ]
        if len(data) > 1:
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]))
    table.setStyle(TableStyle(commands))
    return table


def _card(label, value, accent, styles):
    card = Table(
        [[_paragraph(label.upper(), styles["callout_title"])],
         [_paragraph(value, styles["callout_value"])]],
        colWidths=[None],
    )
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 2.4, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
    ]))
    return card


def _banner(period, loja, styles, width):
    title = _paragraph("EXECUTIVE REPORT<br/><font size='11'>Stock and sales</font>", styles["title"], markup=True)
    brand = _paragraph("MIX MODA  /  INSIGHTS", styles["brand"])
    metadata = _paragraph(
        f"PERIOD<br/><b>{escape(period[0].strftime('%m/%d/%Y'))} to {escape(period[1].strftime('%m/%d/%Y'))}</b>"
        f"<br/><br/>VIEW<br/><b>{escape(str(loja))}</b>", styles["meta"], markup=True
    )
    table = Table([[ [brand, title], metadata ]], colWidths=[width * 0.69, width * 0.31])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEBEFORE", (0, 0), (0, 0), 4, GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 16),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("RIGHTPADDING", (1, 0), (1, 0), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 13),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
    ]))
    return table


def _section_heading(text, styles, note=None):
    cells = [_paragraph(text, styles["section"])]
    if note:
        cells.append(_paragraph(note, styles["muted"]))
        row = Table([cells], colWidths=[None, 245], hAlign="LEFT")
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return row
    return cells[0]


def _safe_float(value):
    try:
        number = float(value)
        return number if isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _group_rows(df, metric):
    if df.empty or "grupo" not in df:
        return []
    return list(
        df.groupby("grupo", dropna=False)[metric].sum()
        .sort_values(ascending=False).head(6).items()
    )


def _summary_cards(df, styles, width):
    if df.empty:
        return []
    sales_group = df.groupby("grupo")["quantidade_vendida"].sum().sort_values(ascending=False)
    no_sales_mask = df["produto_sem_venda"] if "produto_sem_venda" in df else df["quantidade_vendida"] <= 0
    no_sales_rows = df[no_sales_mask]
    no_sales_count = len(no_sales_rows)
    no_sales_value = _safe_float(no_sales_rows["valor_estoque"].sum())
    ruptures = int(df["ruptura"].sum())
    facts = []
    if len(sales_group):
        share = sales_group.iloc[0] / max(float(df["quantidade_vendida"].sum()), 1) * 100
        facts.append(("Top volume", f"{sales_group.index[0]} leads with {fmt_number(sales_group.iloc[0], 0)} units ({share:.0f}% of sales).", BLUE))
    facts.append(("Idle stock", f"{fmt_number(no_sales_count, 0)} products without sales add up to {fmt_money(no_sales_value)} in stock.", TEAL))
    facts.append(("Restock action", f"{fmt_number(ruptures, 0)} products are out of stock after selling in the period.", PINK))
    cards = []
    card_width = width / len(facts)
    for title, body, accent in facts:
        box = Table([
            [_paragraph(title.upper(), styles["callout_title"])],
            [_paragraph(body, styles["body"])],
        ], colWidths=[card_width - 10])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
            ("TOPPADDING", (0, 1), (-1, 1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
        ]))
        cards.append(box)
    row = Table([cards], colWidths=[width / len(cards)] * len(cards))
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [row]


def _store_table(df, styles, width):
    grouped = df.groupby("loja", as_index=False, dropna=False).agg(
        unidades=("quantidade_vendida", "sum"),
        receita=("valor_vendido", "sum"),
        estoque=("quantidade_estoque", "sum"),
        capital=("valor_estoque", "sum"),
    ).sort_values("receita", ascending=False)
    total_revenue = max(float(grouped["receita"].sum()), 1)
    headers = ["Store", "Units sold", "Revenue", "Share", "Current stock", "Capital in stock"]
    data = [[_paragraph(h, styles["table_head"]) for h in headers]]
    for _, row in grouped.iterrows():
        share = float(row.receita) / total_revenue * 100
        data.append([
            _paragraph(str(row.loja), styles["table_bold"]),
            fmt_number(row.unidades, 0), fmt_money(row.receita), f"{share:.1f}%",
            fmt_number(row.estoque, 0), fmt_money(row.capital),
        ])
    widths = [width * .20, width * .14, width * .18, width * .13, width * .14, width * .21]
    return _table(data, widths)


def _critical_table(df, styles, width, limit=20):
    critical_rows = ranked_critical(df, limit)
    headers = ["Product", "Group", "Store", "Stock", "Sold", "Status"]
    data = [[_paragraph(h, styles["table_head"]) for h in headers]]
    for _, row in critical_rows.iterrows():
        data.append([
            _paragraph(str(row.descricao), styles["table"]),
            _paragraph(str(row.grupo), styles["table"]),
            _paragraph(str(row.loja), styles["table"]),
            fmt_number(row.quantidade_estoque, 0),
            fmt_number(row.quantidade_vendida, 0),
            _paragraph(str(row.status_estoque), styles["table_bold"]),
        ])
    widths = [width * .34, width * .23, width * .18, width * .08, width * .08, width * .09]
    table = _table(data, widths, paddings=5)
    if len(data) > 1:
        table.setStyle(TableStyle([
            ("TEXTCOLOR", (5, 1), (5, -1), PINK),
            ("FONTNAME", (5, 1), (5, -1), "Helvetica-Bold"),
        ]))
    return table, len(critical_rows)


def _idle_stock_table(df, styles, width, limit=20):
    rows = idle_stock(df, limit)
    headers = ["#", "Product", "Group", "Store", "Stock", "Unit cost", "Idle value"]
    head_right = ParagraphStyle("idle_head_right", parent=styles["table_head"], alignment=TA_RIGHT)
    data = [[_paragraph(h, head_right if i >= 4 else styles["table_head"]) for i, h in enumerate(headers)]]
    for position, (_, row) in enumerate(rows.iterrows(), start=1):
        quantity = _safe_float(row.quantidade_estoque)
        value = _safe_float(row.valor_estoque)
        data.append([
            str(position),
            _paragraph(str(row.descricao), styles["table"]),
            _paragraph(str(row.grupo), styles["table"]),
            _paragraph(str(row.loja), styles["table"]),
            fmt_number(quantity, 0),
            fmt_money(value / quantity if quantity else 0),
            fmt_money(value),
        ])
    widths = [22, width * .33, width * .2, width * .14, width * .08, width * .1, None]
    widths[-1] = width - sum(widths[:-1])
    table = _table(data, widths, paddings=5)
    if len(data) > 1:
        table.setStyle(TableStyle([
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 1), (0, -1), 7.2),
            ("FONTSIZE", (4, 1), (-1, -1), 7.6),
            ("TEXTCOLOR", (0, 1), (0, -1), MUTED),
            ("TEXTCOLOR", (4, 1), (5, -1), INK),
            ("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (6, 1), (6, -1), GOLD),
            ("FONTNAME", (6, 1), (6, -1), "Helvetica-Bold"),
        ]))
    return table, len(rows)


def _audit_table(audit, styles, width):
    items = [
        ("Stock items", audit.get("produtos_estoque", 0), BLUE),
        ("Sales rows", audit.get("produtos_vendas", 0), CYAN),
        ("Matches", audit.get("vendas_correspondentes", 0), TEAL),
        ("Unmatched keys", audit.get("vendas_sem_correspondencia", 0), PINK),
        ("Invalid barcodes", audit.get("codigos_invalidos", 0), GOLD),
        ("Ignored records", audit.get("produtos_ignorados", 0), BLUE),
    ]
    cards = [_card(label, fmt_number(value, 0), color, styles) for label, value, color in items]
    card_width = width / 3
    row = Table([cards[:3], cards[3:]], colWidths=[card_width] * 3)
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return row


def _unmatched_table(audit, styles, width):
    items = audit.get("vendas_sem_correspondencia_itens", [])
    if not items:
        return _paragraph("Every sales item was matched to stock.", styles["body"])

    items = sorted(
        items,
        key=lambda item: (
            -_safe_float(item.get("quantidade_vendida", 0)),
            str(item.get("descricao", "")).casefold(),
        ),
    )[:20]
    headers = ["Barcode", "Product description", "Store", "Units sold"]
    data = [[_paragraph(header, styles["table_head"]) for header in headers]]
    for item in items:
        data.append([
            _paragraph(item.get("codigo_barras", ""), styles["table"]),
            _paragraph(item.get("descricao", ""), styles["table_bold"]),
            _paragraph(item.get("loja", ""), styles["table"]),
            fmt_number(item.get("quantidade_vendida", 0), 0),
        ])
    return _table(data, [width * .19, width * .46, width * .20, width * .15], paddings=5)


def _audit_legend(styles, width):
    definitions = [
        ("Stock items", "Unique products with a valid barcode and description, after consolidating stock."),
        ("Sales rows", "Product records read from the sales file after cleaning."),
        ("Matches", "Barcode + description combinations found in both stock and sales."),
        ("Unmatched keys", "Barcode + description combinations from sales that were not found in stock."),
        ("Invalid barcodes", "Stock or sales records without a usable barcode."),
        ("Ignored records", "Rows dropped because the description starts with “PECA” (loose part) or “CODIGO DESATIVADO” (disabled code), or because of a legacy 3–4 digit code such as 313, 315 or 3191."),
    ]
    cells = [
        _paragraph(f"<b>{escape(title)}:</b> {escape(description)}", styles["legend"], markup=True)
        for title, description in definitions
    ]
    rows = [[cells[index], cells[index + 1]] for index in range(0, len(cells), 2)]
    table = Table(rows, colWidths=[width / 2, width / 2], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def export_dashboard_pdf(path, df, period, loja, audit):
    """Create a polished, executive-facing report with a summary and action views."""
    page_width, _ = landscape(A4)
    margin = 15 * mm
    content_width = page_width - 2 * margin
    styles = _stylebook()
    doc = SimpleDocTemplate(
        path, pagesize=landscape(A4),
        rightMargin=margin, leftMargin=margin,
        topMargin=18 * mm, bottomMargin=17 * mm,
        title="Mix Moda Insights - Executive report",
        author="Mix Moda Insights",
        subject="Stock and sales report",
    )
    story = []

    # Page 1 - an executive overview with financial and operational indicators.
    story.extend([_banner(period, loja, styles, content_width), Spacer(1, 12)])
    total_sales = _safe_float(df["valor_vendido"].sum()) if not df.empty else 0
    total_units = _safe_float(df["quantidade_vendida"].sum()) if not df.empty else 0
    stock_units = _safe_float(df["quantidade_estoque"].sum()) if not df.empty else 0
    stock_value = _safe_float(df["valor_estoque"].sum()) if not df.empty else 0
    rupture_count = int(df["ruptura"].sum()) if not df.empty else 0
    kpi_specs = [
        ("Revenue", fmt_money(total_sales), BLUE),
        ("Units sold", fmt_number(total_units, 0), TEAL),
        ("Current stock", fmt_number(stock_units, 0), CYAN),
        ("Capital in stock", fmt_money(stock_value), GOLD),
        ("Stockouts", fmt_number(rupture_count, 0), PINK),
    ]
    kpis = [_card(label, value, accent, styles) for label, value, accent in kpi_specs]
    kpi_row = Table([kpis], colWidths=[content_width / len(kpis)] * len(kpis))
    kpi_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([kpi_row, Spacer(1, 16), _section_heading("Executive overview", styles), Spacer(1, 3)])

    group_sales = _group_rows(df, "quantidade_vendida")
    group_stock = _group_rows(df, "valor_estoque")
    chart_width = (content_width - 14) / 2
    charts = [
        HorizontalBars("Sales by group | units", group_sales, lambda v: fmt_number(v, 0), TEAL, chart_width),
        HorizontalBars("Capital in stock by group", group_stock, lambda v: fmt_money(v, 0), BLUE, chart_width),
    ]
    chart_panels = []
    for chart in charts:
        panel = Table([[chart]], colWidths=[chart_width - 8])
        panel.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        chart_panels.append(panel)
    chart_row = Table([chart_panels], colWidths=[chart_width, chart_width])
    chart_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([chart_row, Spacer(1, 13)])
    story.extend(_summary_cards(df, styles, content_width))

    # Page 2 - store performance and the products that drove the period.
    story.extend([PageBreak(), _section_heading("Sales performance", styles,
                                                "Revenue from the sales spreadsheet (column G)."),
                  _store_table(df, styles, content_width), Spacer(1, 16)])
    story.extend([PageBreak(), _section_heading("Top products", styles,
                                  "Top 20 ranked by units sold and revenue.")])
    top = top_sold(df, 20) if not df.empty else df
    headers = ["#", "Product", "Store", "Group", "Units", "Revenue", "Stock"]
    data = [[_paragraph(h, styles["table_head"]) for h in headers]]
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        data.append([
            str(rank),
            _paragraph(str(row.descricao), styles["table_bold"]),
            _paragraph(str(row.loja), styles["table"]),
            _paragraph(str(row.grupo), styles["table"]),
            fmt_number(row.quantidade_vendida, 0),
            fmt_money(row.valor_vendido),
            fmt_number(row.quantidade_estoque, 0),
        ])
    story.append(_table(data, [25, content_width * .29, content_width * .13,
                               content_width * .22, 58, content_width * .16, 48]))

    # Page 3 - concrete replenishment actions and data-quality context.
    story.extend([PageBreak(), _section_heading("Stock priorities", styles,
                                                "Out-of-stock and critical items, prioritized by sales."),
                  Spacer(1, 2)])
    critical, shown = _critical_table(df, styles, content_width)
    story.extend([critical, Spacer(1, 13)])
    if shown == 0:
        story.append(_paragraph("No product is classified as critical, low or out of stock.", styles["body"]))

    # Page 4 - idle capital: no sales in the period and a lot of stock.
    idle_all = df[(df.quantidade_estoque > 0) & (df.quantidade_vendida <= 0)]
    story.extend([PageBreak(), _section_heading("Idle stock", styles,
                                                "Top 20 products with no sales in the period, by largest quantity in stock."),
                  _paragraph(
                      f"{fmt_number(len(idle_all), 0)} products sold nothing in the period, totaling "
                      f"{fmt_number(idle_all.quantidade_estoque.sum(), 0)} units and "
                      f"{fmt_money(idle_all.valor_estoque.sum())} sitting idle in stock (at cost).", styles["muted"]
                  ), Spacer(1, 5)])
    idle_table, idle_shown = _idle_stock_table(df, styles, content_width)
    story.append(idle_table if idle_shown else _paragraph(
        "Every product with stock sold something in the period.", styles["body"]))
    unmatched_items = (audit or {}).get("vendas_sem_correspondencia_itens", [])
    story.extend([PageBreak(), _section_heading("Sales not matched to stock", styles),
                  _paragraph(
                      f"{len(unmatched_items)} sales combinations were not found in stock. "
                      "The table lists the 20 items with the highest units sold for review.", styles["muted"]
                  ), Spacer(1, 5),
                  _unmatched_table(audit or {}, styles, content_width),
                  PageBreak(), _section_heading("Data quality and coverage", styles),
                  _audit_table(audit or {}, styles, content_width), Spacer(1, 5),
                  _section_heading("Indicator glossary", styles),
                  _audit_legend(styles, content_width), Spacer(1, 5)])
    story.append(_paragraph(
        "The barcode identifies the product when it is unique in stock; barcodes linked to "
        "different descriptions use the description as a tie-breaker. Unmatched sales are "
        "left out of the product indicators.", styles["muted"]
    ))

    def page_chrome(canvas, document):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, landscape(A4)[1] - 3, landscape(A4)[0], 3, fill=1, stroke=0)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(margin, 11 * mm, page_width - margin, 11 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawString(margin, 7 * mm, "MIX MODA  |  EXECUTIVE REPORT")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(page_width - margin, 7 * mm, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)

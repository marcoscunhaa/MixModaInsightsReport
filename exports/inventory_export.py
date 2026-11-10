"""Excel "Estoque completo": resumo, tabela dinâmica, aba geral e uma aba por loja.

- **Resumo**: números da rede, tabela por loja e por grupo (com atalhos para as abas).
- **Tabela dinâmica**: tabela dinâmica de verdade (Excel, WPS e LibreOffice), com
  Grupo › Subclasse › Produto nas linhas e as lojas nas colunas. Abre fechada nos
  grupos: o ⊞ ao lado do grupo (ou dois cliques no nome) abre as subclasses, e a
  subclasse abre os produtos. A fonte é a aba oculta **Dados**.
- **Geral** e uma aba por loja: tabela do Excel com filtro em cada coluna.

Visual nas cores da Mix Moda: faixa vermelha com fio amarelo, cabeçalhos amarelos e
linhas alternadas em creme. Fonte Arial, que existe no Excel, no WPS e no LibreOffice.
"""
from datetime import datetime
from pathlib import Path
import re
from xml.sax.saxutils import quoteattr

from lxml import etree
from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule, FormulaRule
from openpyxl.pivot.cache import CacheDefinition
from openpyxl.pivot.record import RecordList
from openpyxl.pivot.table import TableDefinition
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.writer.theme import theme_xml

from core.inventory import PRICE_CATALOG, PRICE_ESTIMATED, PRICE_SALES, PRICE_SYSTEM, inventory_rows
from core.stores import order_stores
from exports.stock_alerts_export import BRAND_RED, BRAND_YELLOW, _sheet_name
from utils.normalization import normalize_text

# Paleta Mix Moda (vermelho e amarelo da fachada) com neutros quentes.
RED = BRAND_RED            # D3203B
RED_DARK = "9E1830"
YELLOW = BRAND_YELLOW      # FFC20E
YELLOW_SOFT = "FFE7A1"
CREAM = "FFF8E7"
BAND = "FFFBF1"
INK = "2E2724"
MUTED = "7D716A"
LINE = "EFE3CB"
WHITE = "FFFFFF"

FONT = "Arial"
MONEY = '"R$" #,##0.00'
UNITS = '#,##0;[Red]-#,##0;0'
SUMMARY_SHEET = "Resumo"
PIVOT_SHEET = "Tabela dinâmica"
GENERAL_SHEET = "Geral"
DATA_SHEET = "Dados"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Abas Geral e por loja.
HEADER_ROW = 3
TABLE_COLUMNS = [
    ("codigo_barras", "Código de barras", 19), ("loja", "Loja", 17),
    ("descricao", "Descrição do produto", 46), ("grupo", "Grupo", 25), ("subclasse", "Subclasse", 25),
    ("estoque", "Estoque", 11), ("preco_venda", "Valor unitário", 15), ("valor_total", "Valor total em estoque", 19),
]

# Fonte da tabela dinâmica (aba Dados).
DATA_COLUMNS = ["Grupo", "Subclasse", "Produto", "Loja", "Estoque", "Valor unitário", "Valor total em estoque"]
PIVOT_TOP = 4

_hair = Side(style="hair", color=LINE)


def _font(size=10, bold=False, color=INK, italic=False):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


def _fill(color):
    return PatternFill("solid", fgColor=color)


def _brand_theme():
    """Tema com as cores da marca: o estilo da tabela dinâmica (destaque 1) sai vermelho."""
    theme = re.sub(r"(<a:accent1>\s*<a:srgbClr val=\")[0-9A-F]{6}", rf"\g<1>{RED}", theme_xml)
    theme = re.sub(r"(<a:accent2>\s*<a:srgbClr val=\")[0-9A-F]{6}", rf"\g<1>{YELLOW}", theme)
    theme = re.sub(r'<a:latin typeface="(Cambria|Calibri)"', f'<a:latin typeface="{FONT}"', theme)
    return theme.encode("utf-8")


def _title(sheet, text, subtitle, last_col, back_link=True):
    """Faixa vermelha com fio amarelo e uma linha de orientação embaixo."""
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    cell = sheet.cell(1, 1, text)
    cell.font = _font(15, True, WHITE)
    cell.alignment = Alignment(vertical="center", indent=1)
    for col in range(1, last_col + 1):
        sheet.cell(1, col).fill = _fill(RED)
        sheet.cell(1, col).border = Border(bottom=Side(style="thick", color=YELLOW))
    sheet.row_dimensions[1].height = 34
    end = last_col - 1 if back_link and last_col > 2 else last_col
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end)
    cell = sheet.cell(2, 1, subtitle)
    cell.font = _font(9, color=MUTED, italic=True)
    cell.alignment = Alignment(vertical="center", indent=1, wrap_text=True)
    sheet.row_dimensions[2].height = 26
    if back_link and last_col > 2:
        link = sheet.cell(2, last_col, "↩ Resumo")
        link.hyperlink = f"#{quote_sheetname(SUMMARY_SHEET)}!A1"
        link.font = Font(name=FONT, size=9, bold=True, color=RED, underline="single")
        link.alignment = Alignment(horizontal="right", vertical="center")


def _header_cell(cell, text, align="center"):
    cell.value = text
    cell.font = _font(10, True, RED_DARK)
    cell.fill = _fill(YELLOW)
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True, indent=1 if align == "left" else 0)
    cell.border = Border(bottom=Side(style="medium", color=RED))


def _page_setup(sheet, title_rows):
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = title_rows
    sheet.oddFooter.center.text = "Mix Moda Insights  •  &A  •  página &P de &N"
    sheet.oddFooter.center.size = 8


def _table_name(label, used):
    base = re.sub(r"[^A-Za-z0-9]+", "_", normalize_text(label)).strip("_").title() or "Loja"
    name, n = f"Estoque_{base}", 2
    candidate = name
    while candidate.lower() in used:
        candidate, n = f"{name}_{n}", n + 1
    used.add(candidate.lower())
    return candidate


# --------------------------------------------------------------------------- Geral / lojas

def _write_table_sheet(sheet, rows, title, subtitle, table_name):
    last_col = len(TABLE_COLUMNS)
    _title(sheet, title, subtitle, last_col)
    sheet.sheet_view.showGridLines = False
    first, last = HEADER_ROW + 1, HEADER_ROW + max(len(rows), 1)
    text_keys = ("loja", "descricao", "grupo", "subclasse")
    for col, (key, text, width) in enumerate(TABLE_COLUMNS, 1):
        _header_cell(sheet.cell(HEADER_ROW, col), text, "left" if key in text_keys else "center")
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.row_dimensions[HEADER_ROW].height = 30

    for r, row in enumerate(rows, first):
        for col, (key, _text, _width) in enumerate(TABLE_COLUMNS, 1):
            cell = sheet.cell(r, col, row[key])
            cell.font = _font(10, bold=key == "descricao")
            cell.alignment = Alignment(
                horizontal="center" if key in ("estoque", "codigo_barras") else
                "right" if key in ("preco_venda", "valor_total") else "left",
                vertical="center", indent=0 if key in ("estoque", "codigo_barras") else 1)
            cell.border = Border(bottom=_hair)
        sheet.cell(r, 1).number_format = "@"
        sheet.cell(r, 6).number_format = UNITS
        sheet.cell(r, 7).number_format = MONEY
        sheet.cell(r, 8).number_format = MONEY

    if rows:
        ref = f"A{HEADER_ROW}:{get_column_letter(last_col)}{last}"
        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False,
                                              showFirstColumn=False, showLastColumn=False, showColumnStripes=False)
        sheet.add_table(table)
        # Linhas alternadas em creme (formatação condicional: vale também no WPS e no LibreOffice).
        sheet.conditional_formatting.add(f"A{first}:{get_column_letter(last_col)}{last}",
                                         FormulaRule(formula=["MOD(ROW(),2)=0"], fill=_fill(BAND)))
    else:
        sheet.cell(first, 1, "Nenhum produto nesta aba.").font = _font(10, color=MUTED, italic=True)
    sheet.freeze_panes = f"B{first}"
    _page_setup(sheet, f"1:{HEADER_ROW}")


# --------------------------------------------------------------------------- Tabela dinâmica

def _product_label(row):
    return f"{row['descricao']}  ·  {row['codigo_barras']}"


def _number(value):
    value = float(value)
    return int(value) if value.is_integer() else round(value, 4)


def _write_data_sheet(sheet, records):
    """Fonte da tabela dinâmica: uma linha por produto × loja (aba oculta)."""
    sheet.append(DATA_COLUMNS)
    for row in records:
        sheet.append([row["grupo"], row["subclasse"], _product_label(row), row["loja"],
                      _number(row["estoque"]), row["preco_venda"], row["valor_total"]])
    sheet.sheet_state = "hidden"


def _ordered_unique(values):
    seen = {}
    for value in values:
        seen.setdefault(value, len(seen))
    return list(seen)


def _pivot_xml(records, stores):
    """XML (cache, registros, tabela) da tabela dinâmica e a lista de grupos na ordem exibida."""
    text_fields = [
        _ordered_unique(r["grupo"] for r in records),
        _ordered_unique(r["subclasse"] for r in records),
        _ordered_unique(_product_label(r) for r in records),
        list(stores),
    ]
    index = [{value: i for i, value in enumerate(items)} for items in text_fields]
    numbers = [[_number(r["estoque"]) for r in records], [r["preco_venda"] for r in records],
               [r["valor_total"] for r in records]]

    fields = []
    for name, items in zip(DATA_COLUMNS[:4], text_fields):
        shared = "".join(f"<s v={quoteattr(str(v))}/>" for v in items)
        fields.append(f'<cacheField name={quoteattr(name)} numFmtId="0">'
                      f'<sharedItems count="{len(items)}">{shared}</sharedItems></cacheField>')
    for name, values in zip(DATA_COLUMNS[4:], numbers):
        integer = ' containsInteger="1"' if all(float(v).is_integer() for v in values) else ""
        fields.append(f'<cacheField name={quoteattr(name)} numFmtId="0"><sharedItems containsSemiMixedTypes="0" '
                      f'containsString="0" containsNumber="1"{integer} minValue="{min(values)}" '
                      f'maxValue="{max(values)}"/></cacheField>')
    # refreshOnLoad: o Excel/WPS recalcula a tabela a partir da aba Dados ao abrir.
    cache = (f'<pivotCacheDefinition xmlns="{NS}" refreshOnLoad="1" refreshedBy="Mix Moda Insights" '
             f'createdVersion="6" refreshedVersion="6" minRefreshableVersion="3" recordCount="{len(records)}">'
             f'<cacheSource type="worksheet"><worksheetSource ref="A1:G{len(records) + 1}" '
             f'sheet="{DATA_SHEET}"/></cacheSource>'
             f'<cacheFields count="{len(DATA_COLUMNS)}">{"".join(fields)}</cacheFields></pivotCacheDefinition>')

    rows_xml = []
    for i, r in enumerate(records):
        keys = (r["grupo"], r["subclasse"], _product_label(r), r["loja"])
        rows_xml.append("<r>" + "".join(f'<x v="{index[f][k]}"/>' for f, k in enumerate(keys))
                        + "".join(f'<n v="{values[i]}"/>' for values in numbers) + "</r>")
    record_list = f'<pivotCacheRecords xmlns="{NS}" count="{len(records)}">{"".join(rows_xml)}</pivotCacheRecords>'

    def items(field, collapsed):
        sd = ' sd="0"' if collapsed else ""  # sd="0": item fechado (não mostra o nível de baixo)
        body = "".join(f'<item{sd} x="{i}"/>' for i in range(len(text_fields[field])))
        return f'<items count="{len(text_fields[field]) + 1}">{body}<item t="default"/></items>'

    def line(i):
        return f'<i><x v="{i}"/></i>' if i else "<i><x/></i>"

    groups, n_stores = len(text_fields[0]), len(stores)
    ref = f"A{PIVOT_TOP}:{get_column_letter(n_stores + 2)}{PIVOT_TOP + groups + 2}"
    table = (
        f'<pivotTableDefinition xmlns="{NS}" name="EstoqueDinamico" cacheId="1" applyNumberFormats="0" '
        'applyBorderFormats="0" applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" '
        'applyWidthHeightFormats="1" dataCaption="Valores" updatedVersion="6" minRefreshableVersion="3" '
        'useAutoFormatting="1" itemPrintTitles="1" createdVersion="6" indent="0" outline="1" outlineData="1" '
        'multipleFieldFilters="0" rowHeaderCaption="Grupo › Subclasse › Produto" colHeaderCaption="Loja">'
        f'<location ref="{ref}" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>'
        f'<pivotFields count="{len(DATA_COLUMNS)}">'
        f'<pivotField axis="axisRow" showAll="0">{items(0, True)}</pivotField>'
        f'<pivotField axis="axisRow" showAll="0">{items(1, True)}</pivotField>'
        f'<pivotField axis="axisRow" showAll="0">{items(2, False)}</pivotField>'
        f'<pivotField axis="axisCol" showAll="0">{items(3, False)}</pivotField>'
        '<pivotField dataField="1" showAll="0"/><pivotField showAll="0"/><pivotField showAll="0"/></pivotFields>'
        '<rowFields count="3"><field x="0"/><field x="1"/><field x="2"/></rowFields>'
        f'<rowItems count="{groups + 1}">{"".join(line(i) for i in range(groups))}<i t="grand"><x/></i></rowItems>'
        '<colFields count="1"><field x="3"/></colFields>'
        f'<colItems count="{n_stores + 1}">{"".join(line(i) for i in range(n_stores))}<i t="grand"><x/></i></colItems>'
        '<dataFields count="1"><dataField name="Unidades em estoque" fld="4" baseField="0" baseItem="0" '
        'numFmtId="3"/></dataFields>'
        '<pivotTableStyleInfo name="PivotStyleMedium2" showRowHeaders="1" showColHeaders="1" '
        'showRowStripes="0" showColStripes="0" showLastColumn="1"/></pivotTableDefinition>'
    )
    return cache, record_list, table, text_fields[0]


def _write_pivot_sheet(sheet, records, stores):
    last_col = 2 + len(stores)
    _title(sheet, "MIX MODA  •  TABELA DINÂMICA DO ESTOQUE",
           "Clique no ⊞ ao lado do grupo (ou dê dois cliques no nome) para abrir as subclasses; na subclasse, "
           "abre os produtos. A seta de Loja escolhe as lojas. Os números são unidades em estoque.",
           max(last_col, 4))
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 58
    for col in range(2, max(last_col, 4) + 1):
        sheet.column_dimensions[get_column_letter(col)].width = 15
    if not records:
        sheet.cell(PIVOT_TOP, 1, "Nenhum produto nesta análise.").font = _font(10, color=MUTED, italic=True)
        return

    cache_xml, records_xml, table_xml, groups = _pivot_xml(records, stores)
    cache = CacheDefinition.from_tree(etree.fromstring(cache_xml.encode("utf-8")))
    cache.records = RecordList.from_tree(etree.fromstring(records_xml.encode("utf-8")))
    pivot = TableDefinition.from_tree(etree.fromstring(table_xml.encode("utf-8")))
    pivot.cache = cache
    sheet._pivots.append(pivot)

    # O mesmo conteúdo já desenhado (fechado nos grupos): aparece certo mesmo
    # num programa que não recalcula a tabela ao abrir.
    totals = {}
    for r in records:
        key = (r["grupo"], r["loja"])
        totals[key] = totals.get(key, 0) + r["estoque"]
    lines = [[("Unidades em estoque", "label"), ("Loja", "label")],
             [("Grupo › Subclasse › Produto", "head")] + [(s, "head") for s in stores] + [("Total geral", "head")]]
    for group in groups:
        values = [totals.get((group, s), 0) for s in stores]
        lines.append([(group, "group")] + [(v, "num") for v in values] + [(sum(values), "num")])
    values = [sum(totals.get((g, s), 0) for g in groups) for s in stores]
    lines.append([("Total geral", "grand")] + [(v, "grand_num") for v in values] + [(sum(values), "grand_num")])
    for i, line in enumerate(lines):
        for j, (value, kind) in enumerate(line):
            cell = sheet.cell(PIVOT_TOP + i, 1 + j, value)
            cell.font = _font(10, kind in ("head", "group", "grand", "grand_num"),
                              WHITE if kind == "head" else RED_DARK if kind.startswith("grand") else INK)
            if kind == "head":
                cell.fill = _fill(RED)
            elif kind.startswith("grand"):
                cell.fill = _fill(CREAM)
            if kind in ("num", "grand_num"):
                cell.number_format = UNITS
    sheet.freeze_panes = sheet.cell(PIVOT_TOP + 2, 2)
    _page_setup(sheet, f"1:{PIVOT_TOP + 1}")


# --------------------------------------------------------------------------- Resumo

def _kpi(sheet, row, col, label, value, fmt, note, accent):
    for c in (col, col + 1):
        for rr in (row, row + 1, row + 2):
            sheet.cell(rr, c).fill = _fill(CREAM)
        sheet.cell(row, c).border = Border(top=Side(style="thick", color=accent))
    for rr, (text, font) in enumerate([(label, _font(8, True, MUTED)), (value, _font(17, True, RED_DARK)),
                                        (note, _font(8, color=MUTED, italic=True))]):
        sheet.merge_cells(start_row=row + rr, start_column=col, end_row=row + rr, end_column=col + 1)
        cell = sheet.cell(row + rr, col, text)
        cell.font = font
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=rr == 2)
        if rr == 1:
            cell.number_format = fmt


def _section(sheet, row, text, last_col):
    cell = sheet.cell(row, 2, text)
    cell.font = _font(12, True, RED_DARK)
    for col in range(2, last_col + 1):
        sheet.cell(row, col).border = Border(bottom=Side(style="medium", color=RED))
    sheet.row_dimensions[row].height = 24


def _summary_table(sheet, row, headers, lines, formats, bars, total=None, links=None):
    """Tabela simples a partir da coluna B; devolve a próxima linha livre."""
    for i, text in enumerate(headers):
        _header_cell(sheet.cell(row, 2 + i), text, "left" if i == 0 else "center")
    sheet.row_dimensions[row].height = 32
    first = row + 1
    for n, line in enumerate(lines):
        r = first + n
        for i, value in enumerate(line):
            cell = sheet.cell(r, 2 + i, value)
            cell.font = _font(10, bold=i == 0)
            cell.fill = _fill(WHITE if n % 2 == 0 else BAND)
            cell.border = Border(bottom=_hair)
            cell.number_format = formats[i]
            cell.alignment = Alignment(horizontal="left" if i == 0 else "center", vertical="center",
                                       indent=1 if i == 0 else 0)
        if links and links[n]:
            cell = sheet.cell(r, 2)
            cell.hyperlink = links[n]
            cell.font = Font(name=FONT, size=10, bold=True, color=RED, underline="single")
        sheet.row_dimensions[r].height = 21
    last = first + len(lines) - 1
    if lines:
        for i in bars:
            letter = get_column_letter(2 + i)
            sheet.conditional_formatting.add(f"{letter}{first}:{letter}{last}",
                                             DataBarRule(start_type="num", start_value=0, end_type="max",
                                                         color="FFD45C", showValue=True))
    r = last + 1
    if total:
        for i, value in enumerate(total):
            cell = sheet.cell(r, 2 + i, value)
            cell.font = _font(10, True, RED_DARK)
            cell.fill = _fill(YELLOW_SOFT)
            cell.border = Border(top=Side(style="medium", color=RED))
            cell.number_format = formats[i]
            cell.alignment = Alignment(horizontal="left" if i == 0 else "center", vertical="center",
                                       indent=1 if i == 0 else 0)
        sheet.row_dimensions[r].height = 23
        r += 1
    return r


def _write_summary(sheet, frame, stores, store_sheets, subtitle):
    sheet.sheet_view.showGridLines = False
    last_col = max(9, 7 + len(stores))
    sheet.column_dimensions["A"].width = 3
    for col in range(2, last_col + 1):
        sheet.column_dimensions[get_column_letter(col)].width = 17 if col <= 9 else 15
    sheet.column_dimensions["B"].width = 34
    _title(sheet, "MIX MODA  •  ESTOQUE COMPLETO", subtitle, last_col, back_link=False)

    products = frame.codigo_barras.nunique()
    units = float(frame.estoque.sum())
    value = float(frame.valor_total.sum())
    zero = int((frame.estoque == 0).sum())
    negative = int((frame.estoque < 0).sum())
    groups = frame.grupo.nunique()
    subclasses = frame[["grupo", "subclasse"]].drop_duplicates().shape[0]
    _kpi(sheet, 4, 2, "PRODUTOS", products, "#,##0", f"{len(frame):,} itens produto × loja".replace(",", "."), RED)
    _kpi(sheet, 4, 4, "UNIDADES EM ESTOQUE", units, "#,##0", f"{zero} zerados • {negative} negativos", YELLOW)
    _kpi(sheet, 4, 6, "VALOR TOTAL EM ESTOQUE", value, MONEY, "estoque × valor unitário de venda", RED)
    _kpi(sheet, 4, 8, "GRUPOS  •  SUBCLASSES", f"{groups}  •  {subclasses}", "@", "classificação do catálogo", YELLOW)
    sheet.row_dimensions[5].height = 32

    row = 8
    _section(sheet, row, "Por loja", last_col)
    lines, links = [], []
    for store in stores:
        part = frame[frame.loja == store]
        part_value = float(part.valor_total.sum())
        lines.append([store, part.codigo_barras.nunique(), float(part.estoque.sum()), part_value,
                      int((part.estoque == 0).sum()), int((part.estoque < 0).sum()),
                      part_value / value if value else 0])
        links.append(f"#{quote_sheetname(store_sheets[store])}!A1")
    row = _summary_table(
        sheet, row + 1,
        ["Loja  (clique para abrir a aba)", "Produtos", "Unidades", "Valor total em estoque", "Zerados",
         "Negativos", "% do valor"],
        lines, ["@", "#,##0", UNITS, MONEY, "#,##0", "#,##0", "0.0%"], bars=[2, 3],
        total=["Total da rede", products, units, value, zero, negative, 1 if value else 0], links=links,
    )

    row += 1
    _section(sheet, row, "Por grupo", last_col)
    lines, links = [], []
    for group in frame.grupo.drop_duplicates():
        part = frame[frame.grupo == group]
        part_value = float(part.valor_total.sum())
        per_store = part.groupby("loja").codigo_barras.nunique()
        lines.append([group, part.subclasse.nunique(), part.codigo_barras.nunique(), float(part.estoque.sum()),
                      part_value, part_value / value if value else 0]
                     + [int(per_store.get(s, 0)) for s in stores])
        links.append(f"#{quote_sheetname(PIVOT_SHEET)}!A1")
    header_row = row + 1
    row = _summary_table(
        sheet, header_row,
        ["Grupo  (clique para a tabela dinâmica)", "Subclasses", "Produtos", "Unidades", "Valor total em estoque",
         "% do valor"] + [f"{s}\nprodutos" for s in stores],
        lines, ["@", "#,##0", "#,##0", UNITS, MONEY, "0.0%"] + ['#,##0;;"—"'] * len(stores), bars=[3, 4],
        links=links,
    )
    for i in range(len(stores)):
        sheet.cell(header_row, 8 + i).fill = _fill(YELLOW_SOFT)

    row += 1
    _section(sheet, row, "Como usar", last_col)
    tips = [
        "▸  Tabela dinâmica: clique no ⊞ ao lado do grupo (ou dê dois cliques no nome) para abrir as subclasses; "
        "na subclasse, abre os produtos, com o estoque de cada loja lado a lado. A seta de Loja escolhe as lojas.",
        "⏷  Geral e abas das lojas: use a seta de cada cabeçalho para filtrar por código, descrição, loja, grupo "
        "ou subclasse (em “Filtros de texto › Contém” dá para buscar parte do nome).",
        f"R$  Valor unitário: preço de venda do {PRICE_SYSTEM.lower()} (coluna F do estoque) → "
        f"{PRICE_SALES.lower()} → {PRICE_CATALOG.lower()} (último valor gravado) → {PRICE_ESTIMATED.lower()}.",
        "≠  Valor total em estoque = estoque × valor unitário. Estoque negativo aparece em vermelho e não entra no valor.",
    ]
    for tip in tips:
        row += 1
        sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=last_col)
        cell = sheet.cell(row, 2, tip)
        cell.font = _font(10)
        cell.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        sheet.row_dimensions[row].height = 30
    _page_setup(sheet, "1:2")


# --------------------------------------------------------------------------- entrada

def export_inventory_xlsx(path, df, catalog=None, period_text="", generated_at=None):
    """Escreve o Excel do estoque completo e devolve o número de produtos (códigos) exportados."""
    frame = inventory_rows(df, catalog)
    stores = order_stores(frame.loja.dropna().unique()) if not frame.empty else []
    stamp = (generated_at or datetime.now()).strftime("%d/%m/%Y às %H:%M")
    subtitle = " • ".join(x for x in (period_text, f"gerado em {stamp}", f"{len(stores)} loja(s)") if x)

    workbook = Workbook()
    workbook.loaded_theme = _brand_theme()
    summary = workbook.active
    summary.title = SUMMARY_SHEET
    pivot_sheet = workbook.create_sheet(PIVOT_SHEET)
    general = workbook.create_sheet(GENERAL_SHEET)
    used_sheets = {n.casefold() for n in (SUMMARY_SHEET, PIVOT_SHEET, GENERAL_SHEET, DATA_SHEET)}
    store_sheets = {store: _sheet_name(store, used_sheets) for store in stores}

    records = frame.to_dict("records")
    used_tables = set()
    _write_table_sheet(general, records, f"MIX MODA  •  ESTOQUE GERAL  •  {frame.codigo_barras.nunique()} produtos",
                       "Todas as lojas juntas: uma linha por produto em cada loja. Filtre pelas setas do cabeçalho.",
                       _table_name("Geral", used_tables))
    for store in stores:
        sheet = workbook.create_sheet(store_sheets[store])
        part = [r for r in records if r["loja"] == store]
        _write_table_sheet(sheet, part, f"MIX MODA  •  {store.upper()}  •  {len(part)} produtos",
                           f"Estoque da loja {store}. Filtre pelas setas do cabeçalho.",
                           _table_name(store, used_tables))
        sheet.sheet_properties.tabColor = YELLOW
    _write_data_sheet(workbook.create_sheet(DATA_SHEET), records)
    _write_pivot_sheet(pivot_sheet, records, stores)
    _write_summary(summary, frame, stores, store_sheets, subtitle)

    summary.sheet_properties.tabColor = RED
    pivot_sheet.sheet_properties.tabColor = RED_DARK
    general.sheet_properties.tabColor = YELLOW
    workbook.active = 0
    workbook.properties.title = "Mix Moda • Estoque completo"
    workbook.properties.creator = "Mix Moda Insights"
    workbook.save(Path(path))
    return int(frame.codigo_barras.nunique()) if not frame.empty else 0

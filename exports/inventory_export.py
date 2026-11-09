"""Excel "Estoque completo": resumo, visão Grupo › Subclasse › Produto, aba geral e uma aba por loja.

- **Resumo**: números da rede, tabela por loja e por grupo (com atalhos para as abas).
- **Por grupo**: funciona como uma tabela dinâmica. Abre fechada nos grupos; o ＋ na
  margem (ou os botões 1 · 2 · 3) abre as subclasses e depois os produtos, com o
  estoque de cada loja em colunas.
- **Geral** e uma aba por loja: tabela do Excel com filtro em cada coluna, campo
  🔎 Buscar que destaca as linhas encontradas e contadores que acompanham o filtro.

Os valores são escritos prontos (sem fórmula), exceto os contadores e o destaque da
busca, que precisam reagir ao que o usuário faz no Excel.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import Outline
from openpyxl.worksheet.table import Table, TableStyleInfo

from core.inventory import (
    PRICE_CATALOG, PRICE_ESTIMATED, PRICE_SALES, PRICE_SYSTEM, inventory_rows,
)
from core.stores import order_stores
from exports.stock_alerts_export import BRAND_RED, BRAND_YELLOW, _sheet_name
from utils.normalization import barcode_sort_key, normalize_text

NAVY = "14284B"
NAVY_SOFT = "1F3A68"
BLUE = "2854D9"
INK = "233451"
MUTED = "718097"
LINE = "DCE4EF"
PALE = "F3F6FB"
GROUP_FILL = "DCE6F5"
GROUP_LINE = "B8C8E6"
SUB_FILL = "F4F7FC"
CREAM = "FFF8E7"
HIGHLIGHT = "FFE89A"
WHITE = "FFFFFF"

FONT = "Aptos"
FONT_DISPLAY = "Aptos Display"
MONEY = '"R$" #,##0.00'
UNITS = '#,##0;[Red]-#,##0;0'
SUMMARY_SHEET = "Resumo"
GROUP_SHEET = "Por grupo"
GENERAL_SHEET = "Geral"

# Tabela das abas Geral e por loja.
HEADER_ROW = 5
TABLE_HEADERS = [
    ("Código de barras", 19), ("Loja", 17), ("Descrição do produto", 46), ("Grupo", 24),
    ("Subclasse", 24), ("Estoque", 11), ("Valor de venda", 15), ("Valor em estoque", 17),
    ("Origem do preço", 19),
]
TABLE_KEYS = ["codigo_barras", "loja", "descricao", "grupo", "subclasse",
              "estoque", "preco_venda", "valor_total", "origem_preco"]

_thin = Side(style="thin", color=LINE)
_hair = Side(style="hair", color=LINE)


def _font(size=10, bold=False, color=INK, italic=False, display=False):
    return Font(name=FONT_DISPLAY if display else FONT, size=size, bold=bold, color=color, italic=italic)


def _fill(color):
    return PatternFill("solid", fgColor=color)


def _title(sheet, text, subtitle, last_col, back_link=True):
    """Faixa da marca (vermelho com fio amarelo) e uma linha de orientação embaixo."""
    letter = get_column_letter(last_col)
    sheet.merge_cells(f"A1:{letter}1")
    sheet["A1"] = text
    sheet["A1"].font = _font(16, True, WHITE, display=True)
    sheet["A1"].alignment = Alignment(vertical="center", indent=1)
    for col in range(1, last_col + 1):
        cell = sheet.cell(1, col)
        cell.fill = _fill(BRAND_RED)
        cell.border = Border(bottom=Side(style="thick", color=BRAND_YELLOW))
    sheet.row_dimensions[1].height = 36
    end = last_col - 1 if back_link and last_col > 2 else last_col
    sheet.merge_cells(f"A2:{get_column_letter(end)}2")
    sheet["A2"] = subtitle
    sheet["A2"].font = _font(10, color=MUTED, italic=True)
    sheet["A2"].alignment = Alignment(vertical="center", indent=1, wrap_text=True)
    sheet.row_dimensions[2].height = 30
    if back_link and last_col > 2:
        link = sheet.cell(2, last_col, "↩ Resumo")
        link.hyperlink = f"#{quote_sheetname(SUMMARY_SHEET)}!A1"
        link.font = Font(name=FONT, size=10, bold=True, color=BLUE, underline="single")
        link.alignment = Alignment(horizontal="right", vertical="center")


def _header_cell(cell, text, align="center"):
    cell.value = text
    cell.font = _font(10, True, WHITE)
    cell.fill = _fill(NAVY)
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True, indent=1 if align == "left" else 0)
    cell.border = Border(bottom=Side(style="medium", color=BRAND_YELLOW))


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
    name = f"Estoque_{base}"
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate, n = f"{name}_{n}", n + 1
    used.add(candidate.lower())
    return candidate


def _price_text(prices):
    """Um preço: o número. Preços diferentes entre lojas: a faixa, em texto."""
    values = sorted({round(p, 2) for p in prices if p > 0})
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    br = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {br(values[0])} – {br(values[-1])}"


# --------------------------------------------------------------------------- Geral / lojas

def _write_table_sheet(sheet, rows, title, subtitle, table_name):
    last_col = len(TABLE_HEADERS)
    _title(sheet, title, subtitle, last_col)
    sheet.sheet_view.showGridLines = False
    first, last = HEADER_ROW + 1, HEADER_ROW + max(len(rows), 1)

    # Linha de busca e contadores que acompanham o filtro.
    label = sheet.cell(3, 1, "🔎  BUSCAR")
    label.font = _font(10, True, NAVY)
    label.alignment = Alignment(horizontal="right", vertical="center", indent=1)
    sheet.merge_cells("B3:D3")
    for col in range(2, 5):
        box = sheet.cell(3, col)
        box.fill = _fill(CREAM)
        box.border = Border(top=Side(style="medium", color=BRAND_YELLOW), bottom=Side(style="medium", color=BRAND_YELLOW),
                            left=Side(style="medium", color=BRAND_YELLOW) if col == 2 else None,
                            right=Side(style="medium", color=BRAND_YELLOW) if col == 4 else None)
    search = sheet["B3"]
    search.font = _font(11, True, INK)
    search.alignment = Alignment(vertical="center", indent=1)
    tip = DataValidation(type="textLength", operator="lessThan", formula1="200", allow_blank=True)
    tip.promptTitle = "Buscar no estoque"
    tip.prompt = "Digite parte do código, do nome, da loja, do grupo ou da subclasse. As linhas encontradas ficam em amarelo. Apague para limpar."
    tip.showInputMessage = True
    sheet.add_data_validation(tip)
    tip.add("B3")
    counters = [
        (5, f"SUBTOTAL(103,A{first}:A{last})", '#,##0" itens visíveis";;"nenhum item visível"'),
        (6, f"SUBTOTAL(109,F{first}:F{last})", '#,##0" un.";[Red]-#,##0" un.";"0 un."'),
        (8, f"SUBTOTAL(109,H{first}:H{last})", MONEY),
    ]
    for col, formula, fmt in counters:
        cell = sheet.cell(3, col, f"={formula}")
        cell.number_format = fmt
        cell.font = _font(10, True, NAVY)
        cell.alignment = Alignment(horizontal="right" if col != 5 else "center", vertical="center")
    sheet.row_dimensions[3].height = 26
    note = sheet.cell(4, 5, "↑ contadores do que está visível (seguem os filtros)")
    note.font = _font(8, color=MUTED, italic=True)
    sheet.row_dimensions[4].height = 16

    for col, (text, width) in enumerate(TABLE_HEADERS, 1):
        _header_cell(sheet.cell(HEADER_ROW, col), text, "left" if col in (2, 3, 4, 5) else "center")
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.row_dimensions[HEADER_ROW].height = 30

    for r, row in enumerate(rows, first):
        for col, key in enumerate(TABLE_KEYS, 1):
            cell = sheet.cell(r, col, row[key])
            cell.font = _font(10, color=MUTED if key == "origem_preco" else INK,
                              italic=key == "origem_preco", bold=key == "descricao")
            cell.alignment = Alignment(horizontal="center" if key in ("estoque", "codigo_barras") else
                                       "right" if key in ("preco_venda", "valor_total") else "left",
                                       vertical="center", indent=1 if key in ("loja", "descricao", "grupo", "subclasse", "origem_preco") else 0)
            cell.border = Border(bottom=_hair)
        sheet.cell(r, 1).number_format = "@"
        sheet.cell(r, 6).number_format = UNITS
        sheet.cell(r, 7).number_format = MONEY
        sheet.cell(r, 8).number_format = MONEY
        if row["origem_preco"] == PRICE_ESTIMATED:
            sheet.cell(r, 7).font = _font(10, color="A35A00", italic=True)

    if rows:
        ref = f"A{HEADER_ROW}:{get_column_letter(last_col)}{last}"
        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False,
                                              showFirstColumn=False, showLastColumn=False, showColumnStripes=False)
        sheet.add_table(table)
        # Busca: destaca as linhas em que o texto aparece no código, nome, loja, grupo ou subclasse.
        sheet.conditional_formatting.add(
            f"A{first}:{get_column_letter(last_col)}{last}",
            FormulaRule(formula=[f'AND(LEN($B$3)>0,ISNUMBER(SEARCH($B$3,$A{first}&" "&$B{first}&" "&$C{first}&" "&$D{first}&" "&$E{first})))'],
                        fill=_fill(HIGHLIGHT), font=Font(bold=True, color=NAVY), stopIfTrue=True),
        )
        sheet.conditional_formatting.add(
            f"A{first}:{get_column_letter(last_col)}{last}",
            FormulaRule(formula=["MOD(ROW(),2)=0"], fill=_fill(PALE)),
        )
    else:
        sheet.cell(first, 1, "Nenhum produto nesta aba.").font = _font(10, color=MUTED, italic=True)
    sheet.freeze_panes = f"B{first}"
    _page_setup(sheet, f"1:{HEADER_ROW}")
    sheet.sheet_view.zoomScale = 95


# --------------------------------------------------------------------------- Por grupo

def _product_entries(frame):
    """Produtos (por código) com estoque por loja, preço e valor, agrupados por grupo › subclasse."""
    tree = {}
    for row in frame.to_dict("records"):
        subs = tree.setdefault(row["grupo"], {})
        products = subs.setdefault(row["subclasse"], {})
        item = products.setdefault(row["codigo_barras"], {
            "codigo_barras": row["codigo_barras"], "nomes": Counter(), "estoque": {}, "precos": [], "valor": 0.0,
        })
        item["nomes"][row["descricao"]] += 1
        item["estoque"][row["loja"]] = item["estoque"].get(row["loja"], 0.0) + row["estoque"]
        item["precos"].append(row["preco_venda"])
        item["valor"] += row["valor_total"]
    return tree


def _write_group_sheet(sheet, frame, stores):
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.outlinePr = Outline(summaryBelow=False, summaryRight=False, showOutlineSymbols=True)
    # Colunas: rótulo, código, produtos, uma por loja, total, preço, valor.
    c_label, c_code, c_count = 1, 2, 3
    c_store = {store: 4 + i for i, store in enumerate(stores)}
    c_total = 4 + len(stores)
    c_price, c_value = c_total + 1, c_total + 2
    last_col = c_value
    _title(sheet, "MIX MODA  •  ESTOQUE POR GRUPO › SUBCLASSE › PRODUTO",
           "Clique no ＋ da margem esquerda para abrir um grupo e depois a subclasse. "
           "Os botões 1 · 2 · 3 no canto superior esquerdo abrem ou fecham todos os níveis de uma vez.",
           last_col)

    top, sub = 4, 5
    for col, text in ((c_label, "Grupo  ›  Subclasse  ›  Produto"), (c_code, "Código de barras"),
                      (c_count, "Produtos"), (c_total, "Estoque total"),
                      (c_price, "Valor de venda"), (c_value, "Valor em estoque")):
        sheet.merge_cells(start_row=top, start_column=col, end_row=sub, end_column=col)
        _header_cell(sheet.cell(top, col), text, "left" if col == c_label else "center")
        sheet.cell(sub, col).border = Border(bottom=Side(style="medium", color=BRAND_YELLOW))
    if stores:
        sheet.merge_cells(start_row=top, start_column=c_store[stores[0]], end_row=top, end_column=c_store[stores[-1]])
        for col in c_store.values():
            sheet.cell(top, col).fill = _fill(NAVY_SOFT)
        head = sheet.cell(top, c_store[stores[0]], "ESTOQUE POR LOJA")
        head.font = _font(9, True, BRAND_YELLOW)
        head.alignment = Alignment(horizontal="center", vertical="center")
        for store, col in c_store.items():
            _header_cell(sheet.cell(sub, col), store)
    sheet.row_dimensions[top].height = 20
    sheet.row_dimensions[sub].height = 30

    tree = _product_entries(frame)

    def write_line(r, label, level, counts, stock, total, price, value, code=""):
        styles = {
            -1: (_fill(CREAM), _font(11, True, BRAND_RED), Border(bottom=Side(style="medium", color=BRAND_YELLOW))),
            0: (_fill(GROUP_FILL), _font(11, True, NAVY), Border(top=Side(style="thin", color=GROUP_LINE), bottom=Side(style="thin", color=GROUP_LINE))),
            1: (_fill(SUB_FILL), _font(10, True, NAVY_SOFT), Border(bottom=_thin)),
            2: (_fill(WHITE), _font(10, color=INK), Border(bottom=_hair)),
        }
        fill, font, border = styles[level]
        values = {c_label: label, c_code: code or None, c_count: counts, c_total: total,
                  c_price: price, c_value: value}
        for store, col in c_store.items():
            values[col] = stock.get(store) if store in stock else ("—" if level == 2 else 0)
        for col in range(1, last_col + 1):
            cell = sheet.cell(r, col, values.get(col))
            cell.fill, cell.font, cell.border = fill, font, border
            cell.alignment = Alignment(horizontal="left" if col == c_label else "center", vertical="center",
                                       indent={-1: 1, 0: 1, 1: 3, 2: 5}[level] if col == c_label else 0)
            if col in c_store.values() or col == c_total:
                cell.number_format = UNITS
                if cell.value == "—":
                    cell.font = _font(10, color="B4BFCF")
            elif col == c_count:
                cell.number_format = "#,##0"
            elif col in (c_price, c_value):
                cell.number_format = MONEY
                cell.alignment = Alignment(horizontal="right", vertical="center")
        sheet.cell(r, c_code).number_format = "@"
        if level >= 1:
            dim = sheet.row_dimensions[r]
            dim.outlineLevel = level
            dim.hidden = True  # abre fechado nos grupos
        sheet.row_dimensions[r].height = {-1: 26, 0: 24, 1: 21, 2: 19}[level]

    def totals(rows_frame):
        stock = {s: float(v) for s, v in rows_frame.groupby("loja").estoque.sum().items()}
        return stock, float(rows_frame.estoque.sum()), float(rows_frame.valor_total.sum())

    stock, total, value = totals(frame)
    r = sub + 1
    write_line(r, "TOTAL GERAL", -1, frame.codigo_barras.nunique(), stock, total, None, value)
    group_rows = {}
    r += 1
    for group, subs in tree.items():
        g_frame = frame[frame.grupo == group]
        stock, total, value = totals(g_frame)
        group_rows[group] = r
        write_line(r, f"▸  {group}", 0, g_frame.codigo_barras.nunique(), stock, total, None, value)
        sheet.row_dimensions[r].collapsed = True
        r += 1
        for subclass, products in subs.items():
            s_frame = g_frame[g_frame.subclasse == subclass]
            stock, total, value = totals(s_frame)
            write_line(r, subclass, 1, len(products), stock, total, None, value)
            sheet.row_dimensions[r].collapsed = True
            r += 1
            for code in sorted(products, key=barcode_sort_key):
                item = products[code]
                name = item["nomes"].most_common(1)[0][0]
                write_line(r, name, 2, None, item["estoque"], sum(item["estoque"].values()),
                           _price_text(item["precos"]), item["valor"], code=code)
                r += 1

    widths = {c_label: 52, c_code: 18, c_count: 11, c_total: 13, c_price: 21, c_value: 18}
    for col in range(1, last_col + 1):
        sheet.column_dimensions[get_column_letter(col)].width = widths.get(col, 14)
    sheet.freeze_panes = sheet.cell(sub + 1, c_count)
    _page_setup(sheet, f"1:{sub}")
    return group_rows


# --------------------------------------------------------------------------- Resumo

def _kpi(sheet, row, col, label, value, fmt, note, accent):
    for c in (col, col + 1):
        for rr in (row, row + 1, row + 2):
            sheet.cell(rr, c).fill = _fill(PALE)
        sheet.cell(row, c).border = Border(top=Side(style="thick", color=accent))
    for rr, (text, font) in enumerate([(label, _font(9, True, MUTED)), (value, _font(18, True, NAVY, display=True)),
                                        (note, _font(9, color=MUTED, italic=True))]):
        sheet.merge_cells(start_row=row + rr, start_column=col, end_row=row + rr, end_column=col + 1)
        cell = sheet.cell(row + rr, col, text)
        cell.font = font
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=rr == 2)
        if rr == 1:
            cell.number_format = fmt


def _section(sheet, row, text, last_col):
    cell = sheet.cell(row, 2, text)
    cell.font = _font(12, True, NAVY, display=True)
    for col in range(2, last_col + 1):
        sheet.cell(row, col).border = Border(bottom=Side(style="medium", color=BRAND_RED))
    sheet.row_dimensions[row].height = 24


def _summary_table(sheet, row, headers, lines, formats, bars, total=None, links=None):
    """Tabela simples a partir da coluna B; devolve a próxima linha livre."""
    for i, text in enumerate(headers):
        _header_cell(sheet.cell(row, 2 + i), text, "left" if i == 0 else "center")
    sheet.row_dimensions[row].height = 26
    first = row + 1
    for n, line in enumerate(lines):
        r = first + n
        for i, value in enumerate(line):
            cell = sheet.cell(r, 2 + i, value)
            cell.font = _font(10, bold=i == 0, color=INK)
            cell.fill = _fill(WHITE if n % 2 == 0 else PALE)
            cell.border = Border(bottom=_hair)
            cell.number_format = formats[i]
            cell.alignment = Alignment(horizontal="left" if i == 0 else "center", vertical="center", indent=1 if i == 0 else 0)
        if links and links[n]:
            cell = sheet.cell(r, 2)
            cell.hyperlink = links[n]
            cell.font = Font(name=FONT, size=10, bold=True, color=BLUE)
        sheet.row_dimensions[r].height = 21
    last = first + len(lines) - 1
    for i in bars:
        if lines:
            letter = get_column_letter(2 + i)
            sheet.conditional_formatting.add(f"{letter}{first}:{letter}{last}",
                                             DataBarRule(start_type="num", start_value=0, end_type="max",
                                                         color="9DB4F0", showValue=True))
    r = last + 1
    if total:
        for i, value in enumerate(total):
            cell = sheet.cell(r, 2 + i, value)
            cell.font = _font(10, True, BRAND_RED)
            cell.fill = _fill(CREAM)
            cell.border = Border(top=Side(style="medium", color=BRAND_YELLOW))
            cell.number_format = formats[i]
            cell.alignment = Alignment(horizontal="left" if i == 0 else "center", vertical="center", indent=1 if i == 0 else 0)
        sheet.row_dimensions[r].height = 23
        r += 1
    return r


def _write_summary(sheet, frame, stores, store_sheets, group_rows, subtitle):
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
    groups, subclasses = frame.grupo.nunique(), frame[["grupo", "subclasse"]].drop_duplicates().shape[0]
    _kpi(sheet, 4, 2, "PRODUTOS", products, "#,##0", f"{len(frame):,} itens produto × loja".replace(",", "."), BRAND_RED)
    _kpi(sheet, 4, 4, "UNIDADES EM ESTOQUE", units, "#,##0", f"{zero} zerados • {negative} negativos", BRAND_YELLOW)
    _kpi(sheet, 4, 6, "VALOR DE VENDA EM ESTOQUE", value, MONEY, "estoque × valor de venda atual", NAVY)
    _kpi(sheet, 4, 8, "GRUPOS  •  SUBCLASSES", f"{groups}  •  {subclasses}", "@", "classificação do catálogo", BLUE)
    sheet.row_dimensions[5].height = 34

    row = 8
    _section(sheet, row, "Por loja", last_col)
    lines, links = [], []
    for store in stores:
        part = frame[frame.loja == store]
        part_value = float(part.valor_total.sum())
        lines.append([store, part.codigo_barras.nunique(), float(part.estoque.sum()), part_value,
                      int((part.estoque == 0).sum()), int((part.estoque < 0).sum()),
                      part_value / value if value else 0])
        links.append(f"#{quote_sheetname(store_sheets[store])}!A1" if store in store_sheets else None)
    row = _summary_table(
        sheet, row + 1,
        ["Loja  (clique para abrir a aba)", "Produtos", "Unidades", "Valor em estoque", "Zerados", "Negativos", "% do valor"],
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
        links.append(f"#{quote_sheetname(GROUP_SHEET)}!A{group_rows[group]}" if group in group_rows else None)
    header_row = row + 1
    row = _summary_table(
        sheet, header_row,
        ["Grupo  (clique para ver)", "Subclasses", "Produtos", "Unidades", "Valor em estoque", "% do valor"]
        + [f"{s}\nprodutos" for s in stores],
        lines, ["@", "#,##0", "#,##0", UNITS, MONEY, "0.0%"] + ["#,##0;;\"—\""] * len(stores), bars=[3, 4],
    )
    for i in range(len(stores)):
        cell = sheet.cell(header_row, 8 + i)
        cell.fill = _fill(NAVY_SOFT)
    sheet.row_dimensions[header_row].height = 32

    row += 1
    _section(sheet, row, "Como usar", last_col)
    tips = [
        "🔎  Geral e abas das lojas: digite no campo BUSCAR (código, nome, loja, grupo ou subclasse) e as linhas encontradas ficam em amarelo.",
        "⏷  Para filtrar de verdade, use a seta de cada cabeçalho (ex.: Loja = Pedras, Grupo = Utilidades). Os contadores acima da tabela mostram só o que está visível.",
        "▸  Por grupo: clique no ＋ da margem esquerda para abrir o grupo, depois a subclasse, até os produtos — com o estoque de cada loja lado a lado.",
        f"R$  Valor de venda: {PRICE_SYSTEM} (preço do sistema, coluna F do estoque) → {PRICE_SALES} → "
        f"{PRICE_CATALOG} (último valor gravado) → {PRICE_ESTIMATED}. A coluna “Origem do preço” mostra qual foi usado.",
        "≠  Estoque negativo aparece em vermelho e não entra no valor em estoque (é venda sem entrada no sistema).",
    ]
    for tip in tips:
        row += 1
        sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=last_col)
        cell = sheet.cell(row, 2, tip)
        cell.font = _font(10, color=INK)
        cell.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        sheet.row_dimensions[row].height = 30
    _page_setup(sheet, "1:2")


# --------------------------------------------------------------------------- entrada

def export_inventory_xlsx(path, df, catalog=None, period_text="", generated_at=None):
    """Escreve o Excel do estoque completo e devolve o número de produtos (códigos) exportados."""
    frame = inventory_rows(df, catalog)
    stores = order_stores(frame.loja.dropna().unique()) if not frame.empty else []
    generated_at = generated_at or datetime.now()
    stamp = generated_at.strftime("%d/%m/%Y às %H:%M")
    base = " • ".join(x for x in (period_text, f"gerado em {stamp}", f"{len(stores)} loja(s)") if x)

    workbook = Workbook()
    summary = workbook.active
    summary.title = SUMMARY_SHEET
    used_sheets = {SUMMARY_SHEET.casefold(), GROUP_SHEET.casefold(), GENERAL_SHEET.casefold()}
    group_sheet = workbook.create_sheet(GROUP_SHEET)
    general = workbook.create_sheet(GENERAL_SHEET)
    store_sheets = {store: _sheet_name(store, used_sheets) for store in stores}

    records = frame.to_dict("records")
    used_tables = set()
    _write_table_sheet(general, records, f"MIX MODA  •  ESTOQUE GERAL  •  {frame.codigo_barras.nunique()} produtos",
                       "Todas as lojas juntas: uma linha por produto em cada loja. Filtre pelas setas do cabeçalho ou use a busca.",
                       _table_name("Geral", used_tables))
    for store in stores:
        sheet = workbook.create_sheet(store_sheets[store])
        part = [r for r in records if r["loja"] == store]
        _write_table_sheet(sheet, part, f"MIX MODA  •  {store.upper()}  •  {len(part)} produtos",
                           f"Estoque da loja {store}. Filtre pelas setas do cabeçalho ou use a busca.",
                           _table_name(store, used_tables))
        sheet.sheet_properties.tabColor = BRAND_YELLOW
    group_rows = _write_group_sheet(group_sheet, frame, stores) if not frame.empty else {}
    _write_summary(summary, frame, stores, store_sheets, group_rows, base)

    summary.sheet_properties.tabColor = BRAND_RED
    group_sheet.sheet_properties.tabColor = NAVY
    general.sheet_properties.tabColor = BLUE
    workbook.active = 0
    workbook.properties.title = "Mix Moda • Estoque completo"
    workbook.properties.creator = "Mix Moda Insights"
    workbook.save(Path(path))
    return int(frame.codigo_barras.nunique()) if not frame.empty else 0

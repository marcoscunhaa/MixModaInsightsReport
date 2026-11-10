"""Planilha modelo para importar alertas de estoque (regras de estoque mínimo).

Abas, nesta ordem (abre em Como usar):
- **Como usar**: os passos.
- **Produtos**: todos os produtos do catálogo com o estoque de cada loja (última
  análise), em tabela com filtro, para achar e copiar códigos.
- **Alertas**: onde o usuário trabalha. Cola o código de barras e a descrição, o grupo
  e o estoque atual aparecem sozinhos (fórmulas que procuram na aba Produtos). Ele só
  informa o estoque mínimo e as lojas. A coluna Situação avisa o que falta. Já vem com
  as regras que existem hoje, para ajustar o limite.

A leitura de volta fica em core/alert_import.py e usa só as colunas que o usuário
preenche (código, mínimo e lojas), não o resultado das fórmulas.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from core.alert_import import (
    HEAD_ALL, HEAD_CODE, HEAD_MINIMUM, SHEET, YES, template_products, template_rule_rows,
)
from core.stores import STORES
from exports.inventory_export import (
    BAND, CREAM, FONT, INK, LINE, MUTED, RED, RED_DARK, WHITE, YELLOW, YELLOW_SOFT,
    _brand_theme, _fill, _font, _header_cell, _page_setup, _title,
)

PRODUCTS_SHEET = "Produtos"
HELP_SHEET = "Como usar"
FIRST_ROW = 5          # primeira linha de dados da aba Alertas
EMPTY_ROWS = 400       # linhas livres além das regras atuais
GREEN = "18794E"
GREEN_SOFT = "E6F4EC"
RED_SOFT = "FDE7EA"
GREY = "F2F0EC"
GREY_INK = "A39A92"

_hair = Side(style="hair", color=LINE)
_input_side = Side(style="thin", color="F1D27A")


def _products_sheet(sheet, products):
    """Catálogo com estoque por loja. Devolve (primeira, última linha, coluna do total, coluna da chave)."""
    headers = [("Código de barras", 19), ("Descrição do produto", 46), ("Grupo", 24), ("Subclasse", 24)]
    headers += [(store, 13) for store in STORES] + [("Estoque total", 13), ("Chave", 16)]
    total_col, key_col = len(headers) - 1, len(headers)
    _title(sheet, "MIX MODA  •  PRODUTOS E ESTOQUE POR LOJA",
           "Todos os produtos do catálogo com o estoque da última análise. Filtre pelas setas, copie o código "
           "e cole na aba Alertas.", total_col, back_link=False)
    sheet.sheet_view.showGridLines = False
    header = 3
    for col, (text, width) in enumerate(headers, 1):
        _header_cell(sheet.cell(header, col), text, "left" if col in (2, 3, 4) else "center")
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.row_dimensions[header].height = 30
    first = header + 1
    for r, product in enumerate(products, first):
        values = [product["codigo_barras"], product["descricao"], product["grupo"], product["subclasse"]]
        stock = [product["estoque"][store] for store in STORES]
        known = [v for v in stock if v is not None]
        values += stock + [sum(known) if known else None]
        for col, value in enumerate(values, 1):
            cell = sheet.cell(r, col, value)
            cell.font = _font(10, bold=col == 2)
            cell.border = Border(bottom=_hair)
            if col >= 5:
                cell.number_format = '#,##0;[Red]-#,##0;0'
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="center" if col == 1 else "left", vertical="center",
                                           indent=0 if col == 1 else 1)
        sheet.cell(r, 1).number_format = "@"
        # Chave numérica: acha o código mesmo que o Excel tenha virado o que foi colado em número
        # ou que falte o zero à esquerda.
        key = product["chave"]
        sheet.cell(r, key_col, int(key) if key.isdigit() and len(key) <= 15 else key)
    last = max(first, first + len(products) - 1)
    if products:
        table = Table(displayName="Produtos", ref=f"A{header}:{get_column_letter(total_col)}{last}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        sheet.add_table(table)
        sheet.conditional_formatting.add(f"A{first}:{get_column_letter(total_col)}{last}",
                                         FormulaRule(formula=["MOD(ROW(),2)=0"], fill=_fill(BAND)))
    sheet.column_dimensions[get_column_letter(key_col)].hidden = True
    sheet.freeze_panes = f"C{first}"
    _page_setup(sheet, f"1:{header}")
    return first, last, total_col, key_col


def _alerts_sheet(sheet, rules, product_range):
    first_p, last_p, total_col, key_col = product_range
    stores = list(STORES)
    # A código | B descrição | C grupo | D estoque atual | E mínimo | F todas | G.. lojas | situação | (match)
    c_code, c_desc, c_group, c_stock, c_min, c_all = 1, 2, 3, 4, 5, 6
    c_store = {store: 7 + i for i, store in enumerate(stores)}
    c_status = 7 + len(stores)
    c_match = c_status + 1
    letter = get_column_letter
    inputs = [c_code, c_min, c_all] + list(c_store.values())

    _title(sheet, "MIX MODA  •  IMPORTAR ALERTAS DE ESTOQUE",
           "Cole o código de barras: a descrição, o grupo e o estoque aparecem sozinhos. Informe o estoque mínimo "
           "e as lojas (deixe as lojas em branco para valer em todas). Depois, no app: Alertas › Importar planilha.",
           c_status, back_link=False)
    sheet.row_dimensions[2].height = 32
    sheet.sheet_view.showGridLines = False

    # Faixa que separa o que o usuário preenche do que é automático.
    def band(start, end, text, fill, color):
        sheet.merge_cells(start_row=3, start_column=start, end_row=3, end_column=end)
        cell = sheet.cell(3, start, text)
        cell.font = _font(8, True, color)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in range(start, end + 1):
            sheet.cell(3, col).fill = _fill(fill)
    band(c_code, c_code, "✎  VOCÊ COLA", YELLOW_SOFT, RED_DARK)
    band(c_desc, c_stock, "AUTOMÁTICO  •  vem da aba Produtos", GREY, GREY_INK)
    band(c_min, c_store[stores[-1]], "✎  VOCÊ DEFINE", YELLOW_SOFT, RED_DARK)
    band(c_status, c_status, "AUTOMÁTICO", GREY, GREY_INK)
    sheet.row_dimensions[3].height = 18

    header = FIRST_ROW - 1
    titles = {c_code: HEAD_CODE, c_desc: "Descrição do produto", c_group: "Grupo", c_stock: "Estoque atual",
              c_min: HEAD_MINIMUM, c_all: HEAD_ALL, c_status: "Situação", c_match: "linha"}
    titles.update({col: store for store, col in c_store.items()})
    widths = {c_code: 20, c_desc: 44, c_group: 22, c_stock: 12, c_min: 13, c_all: 13, c_status: 28, c_match: 8}
    for col, text in titles.items():
        _header_cell(sheet.cell(header, col), text, "left" if col in (c_desc, c_group, c_status) else "center")
        sheet.column_dimensions[letter(col)].width = widths.get(col, 13)
    for col in (c_desc, c_group, c_stock, c_status):
        sheet.cell(header, col).fill = _fill("E9E4DC")
        sheet.cell(header, col).font = _font(10, True, "6B625B")
    sheet.row_dimensions[header].height = 32
    sheet.column_dimensions[letter(c_match)].hidden = True

    prefilled = template_rule_rows(rules)
    last = FIRST_ROW + len(prefilled) + EMPTY_ROWS - 1
    P = f"'{PRODUCTS_SHEET}'!"
    keys = f"{P}${letter(key_col)}${first_p}:${letter(key_col)}${last_p}"
    codes = f"{P}$A${first_p}:$A${last_p}"

    def lookup(col, r):
        return f'=IF(N(${letter(c_match)}{r})=0,"",INDEX({P}${letter(col)}${first_p}:${letter(col)}${last_p},${letter(c_match)}{r}))'

    stores_range = lambda r: f"{letter(c_store[stores[0]])}{r}:{letter(c_store[stores[-1]])}{r}"
    for r in range(FIRST_ROW, last + 1):
        a = f"$A{r}"
        sheet.cell(r, c_match, f'=IF(TRIM({a}&"")="","",IFERROR(MATCH(--TRIM({a}&""),{keys},0),'
                               f'IFERROR(MATCH(TRIM({a}&""),{codes},0),0)))')
        sheet.cell(r, c_desc, lookup(2, r))
        sheet.cell(r, c_group, lookup(3, r))
        sheet.cell(r, c_stock, lookup(total_col, r))
        m, e, f = f"${letter(c_match)}{r}", f"${letter(c_min)}{r}", f"${letter(c_all)}{r}"
        marked = f'COUNTIF({stores_range(r)},"{YES}")'
        sheet.cell(r, c_status,
                   f'=IF(TRIM({a}&"")="",IF({e}="","","⚠  Falta o código"),IF(N({m})=0,"⚠  Código não encontrado",'
                   f'IF({e}="","✎  Informe o mínimo",IF(OR({f}="{YES}",{marked}=0),"✓  Todas as lojas",'
                   f'"✓  "&{marked}&IF({marked}=1," loja"," lojas")))))')
        for col in range(1, c_status + 1):
            cell = sheet.cell(r, col)
            cell.border = Border(bottom=_hair, left=_input_side if col in inputs else None,
                                 right=_input_side if col in inputs else None)
            cell.font = _font(10, bold=col in (c_code, c_desc, c_min), color=INK if col in inputs or col == c_desc else MUTED)
            if col in inputs:
                cell.fill = _fill(CREAM)
            cell.alignment = Alignment(horizontal="left" if col in (c_desc, c_group, c_status) else "center",
                                       vertical="center", indent=1 if col in (c_desc, c_group, c_status) else 0)
        sheet.cell(r, c_code).number_format = "@"
        sheet.cell(r, c_stock).number_format = '#,##0;[Red]-#,##0;0'
        sheet.cell(r, c_min).number_format = "0"
        sheet.cell(r, c_min).font = _font(11, True, RED_DARK)

    for r, rule in enumerate(prefilled, FIRST_ROW):
        sheet.cell(r, c_code, str(rule["codigo_barras"]))
        sheet.cell(r, c_min, rule["estoque_minimo"])
        if rule["lojas"] == ["*"]:
            sheet.cell(r, c_all, YES)
        for store in rule["lojas"]:
            if store in c_store:
                sheet.cell(r, c_store[store], YES)

    area = lambda c1, c2: f"{letter(c1)}{FIRST_ROW}:{letter(c2)}{last}"
    # Dicas e validação nas colunas que o usuário preenche.
    tip_code = DataValidation(type="textLength", operator="lessThan", formula1="60", allow_blank=True)
    tip_code.promptTitle, tip_code.prompt = "Código de barras", "Cole o código. A descrição aparece ao lado; se não aparecer, confira na aba Produtos."
    minimum = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    minimum.promptTitle, minimum.prompt = "Estoque mínimo", "Avisar quando o estoque ficar igual ou abaixo deste número."
    minimum.errorTitle, minimum.error = "Estoque mínimo", "Use um número inteiro, zero ou maior."
    minimum.showErrorMessage = True
    every = DataValidation(type="list", formula1=f'"{YES},Não"', allow_blank=True)
    every.promptTitle, every.prompt = "Todas as lojas", "Sim = vale para todas. Deixe em branco e marque as lojas ao lado para escolher."
    store = DataValidation(type="list", formula1=f'"{YES}"', allow_blank=True)
    store.promptTitle, store.prompt = "Loja", "Marque Sim nas lojas desejadas. Sem nenhuma marcada, vale para todas."
    for validation, ref in ((tip_code, area(c_code, c_code)), (minimum, area(c_min, c_min)),
                            (every, area(c_all, c_all)), (store, area(c_store[stores[0]], c_store[stores[-1]]))):
        validation.showInputMessage = True
        sheet.add_data_validation(validation)
        validation.add(ref)

    # Situação em verde (pronto) ou vermelho (problema); lojas apagadas quando vale para todas.
    status = area(c_status, c_status)
    first_status = f"{letter(c_status)}{FIRST_ROW}"
    sheet.conditional_formatting.add(status, FormulaRule(formula=[f'LEFT({first_status},1)="✓"'],
                                                         fill=_fill(GREEN_SOFT), font=Font(name=FONT, bold=True, color=GREEN)))
    sheet.conditional_formatting.add(status, FormulaRule(formula=[f'LEFT({first_status},1)="⚠"'],
                                                         fill=_fill(RED_SOFT), font=Font(name=FONT, bold=True, color=RED)))
    sheet.conditional_formatting.add(status, FormulaRule(formula=[f'LEFT({first_status},1)="✎"'],
                                                         font=Font(name=FONT, bold=True, color="B07A00")))
    sheet.conditional_formatting.add(
        area(c_code, c_code),
        FormulaRule(formula=[f'AND(TRIM($A{FIRST_ROW}&"")<>"",N(${letter(c_match)}{FIRST_ROW})=0)'],
                    fill=_fill(RED_SOFT), font=Font(name=FONT, bold=True, color=RED)))
    sheet.conditional_formatting.add(
        area(c_store[stores[0]], c_store[stores[-1]]),
        FormulaRule(formula=[f'${letter(c_all)}{FIRST_ROW}="{YES}"'], fill=_fill(GREY), font=Font(name=FONT, color=GREY_INK)))
    sheet.conditional_formatting.add(
        area(c_all, c_store[stores[-1]]),
        FormulaRule(formula=[f'{letter(c_all)}{FIRST_ROW}="{YES}"'], fill=_fill(YELLOW), font=Font(name=FONT, bold=True, color=RED_DARK)))

    sheet.freeze_panes = f"B{FIRST_ROW}"
    sheet.auto_filter.ref = f"A{header}:{letter(c_status)}{last}"
    _page_setup(sheet, f"1:{header}")
    return len(prefilled)


def _help_sheet(sheet):
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 3
    sheet.column_dimensions["B"].width = 7
    sheet.column_dimensions["C"].width = 92
    _title(sheet, "MIX MODA  •  COMO IMPORTAR ALERTAS", "Quatro passos, sem digitar nome de produto.", 3, back_link=False)
    steps = [
        ("1", "Ache o produto", "Na aba Produtos, filtre pela seta do cabeçalho (nome, grupo, subclasse) e copie o código de barras."),
        ("2", "Cole o código", "Na aba Alertas, cole o código na coluna amarela. Descrição, grupo e estoque atual aparecem sozinhos."),
        ("3", "Defina o alerta", "Informe o estoque mínimo: o alerta dispara quando o estoque ficar igual ou abaixo dele. "
                                 "Em Todas as lojas, Sim vale para a rede; para só algumas, marque Sim nas lojas desejadas "
                                 "(sem nenhuma marcada, também vale para todas)."),
        ("4", "Importe no app", "Salve a planilha e, no app, abra Alertas › Importar planilha. Você vê a prévia "
                                "(novas, atualizadas, com problema) antes de confirmar."),
    ]
    row = 4
    for number, title, text in steps:
        badge = sheet.cell(row, 2, number)
        badge.font = _font(16, True, WHITE)
        badge.fill = _fill(RED)
        badge.alignment = Alignment(horizontal="center", vertical="center")
        sheet.merge_cells(start_row=row, start_column=2, end_row=row + 1, end_column=2)
        head = sheet.cell(row, 3, title)
        head.font = _font(12, True, RED_DARK)
        head.alignment = Alignment(vertical="bottom", indent=1)
        body = sheet.cell(row + 1, 3, text)
        body.font = _font(10, color=INK)
        body.alignment = Alignment(vertical="top", wrap_text=True, indent=1)
        for r in (row, row + 1):
            sheet.cell(r, 3).fill = _fill(CREAM)
        sheet.cell(row, 3).border = Border(top=Side(style="medium", color=YELLOW))
        sheet.row_dimensions[row].height = 22
        sheet.row_dimensions[row + 1].height = 34
        row += 3
    notes = [
        "•  As regras que já existem vêm preenchidas na aba Alertas: é só mudar o mínimo e importar de novo.",
        "•  Código repetido na planilha: vale a última linha. Apagar uma linha aqui não apaga a regra no app.",
        "•  A coluna Situação mostra ✓ quando a linha está pronta e ⚠ quando falta algo ou o código não existe.",
    ]
    for note in notes:
        cell = sheet.cell(row, 3, note)
        cell.font = _font(10, color=MUTED, italic=True)
        cell.alignment = Alignment(wrap_text=True, indent=1, vertical="center")
        sheet.row_dimensions[row].height = 20
        row += 1
    _page_setup(sheet, "1:2")
    sheet.page_setup.orientation = "portrait"


def export_alert_template_xlsx(path, catalog, rules=None, snapshot=None):
    """Escreve a planilha modelo. Devolve (produtos no catálogo, regras atuais já preenchidas)."""
    products = template_products(catalog, snapshot)
    workbook = Workbook()
    workbook.loaded_theme = _brand_theme()
    # Ordem das abas: Como usar › Produtos › Alertas (abre em Como usar).
    help_sheet = workbook.active
    help_sheet.title = HELP_SHEET
    products_sheet = workbook.create_sheet(PRODUCTS_SHEET)
    alerts = workbook.create_sheet(SHEET)
    product_range = _products_sheet(products_sheet, products)
    prefilled = _alerts_sheet(alerts, rules, product_range)
    _help_sheet(help_sheet)
    alerts.sheet_properties.tabColor = RED
    products_sheet.sheet_properties.tabColor = YELLOW
    help_sheet.sheet_properties.tabColor = RED_DARK
    workbook.active = 0
    alerts.sheet_view.selection[0].activeCell = f"A{FIRST_ROW + prefilled}"
    alerts.sheet_view.selection[0].sqref = f"A{FIRST_ROW + prefilled}"
    workbook.properties.title = "Mix Moda • Importar alertas de estoque"
    workbook.properties.creator = "Mix Moda Insights"
    workbook.save(Path(path))
    return len(products), prefilled

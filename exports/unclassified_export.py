"""Excel de produtos sem classificação (uma aba por loja) e leitura do Excel preenchido.

Cada aba traz o que é preciso para cadastrar: código, descrição, estoque, preços,
as colunas GRUPO e SUBCLASSE a preencher pelo cliente (com
lista suspensa). O mesmo arquivo, preenchido, volta para o app em
Explorar estoque › Importar planilha de classificação.
"""
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from core.stores import order_stores, store_sort_key
from core.unclassified import is_unclassified, merge_by_barcode, unclassified_rows
from exports.stock_alerts_export import BRAND_YELLOW, _sheet_name, brand_title_row
from utils.normalization import barcode_sort_key, normalize_barcode, normalize_text, to_number

NAVY = "14284B"
BLUE = "2854D9"
ORANGE = "E8742A"
PALE = "F3F6FB"
FILL_ME = "FFF7E0"
WHITE = "FFFFFF"
INK = "233451"
MUTED = "718097"
LINE = "DCE4EF"
GREEN = "E7F5EE"
GREEN_INK = "18794E"

LISTS_SHEET = "Listas"
HEADER_ROW = 4
HEADERS = [
    "Código de barras", "Descrição", "Loja", "Também em", "Estoque", "Vendas no período",
    "Preço de compra", "Preço de venda",
    "GRUPO", "SUBCLASSE",
]
WIDTHS = [20, 42, 17, 26, 10, 11, 13, 13, 28, 28]
COL = {name: i + 1 for i, name in enumerate(HEADERS)}


def _tree(catalog):
    tree = {}
    for product in (catalog or {}).get("produtos", []):
        g, s = product.get("grupo", ""), product.get("subclasse", "")
        if g and s and not is_unclassified(g) and not is_unclassified(s):
            tree.setdefault(g, set()).add(s)
    return {g: sorted(subs, key=normalize_text) for g, subs in sorted(tree.items(), key=lambda kv: normalize_text(kv[0]))}


def _lists_sheet(workbook, tree):
    """Aba oculta com Grupo|Subclasse (para a lista dependente) e a lista de grupos."""
    sheet = workbook.create_sheet(LISTS_SHEET)
    sheet["A1"], sheet["B1"], sheet["D1"] = "Grupo", "Subclasse", "Grupos"
    row = 2
    for group, subs in tree.items():
        for sub in subs:
            sheet.cell(row, 1, group); sheet.cell(row, 2, sub); row += 1
    for i, group in enumerate(tree, 2):
        sheet.cell(i, 4, group)
    sheet.sheet_state = "hidden"
    return max(row - 1, 2), max(len(tree) + 1, 2)


def _guide_sheet(workbook, total, stores):
    sheet = workbook.create_sheet("Como usar", 0)
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 110
    lines = [
        ("MIX MODA  •  CADASTRO DE PRODUTOS SEM CLASSIFICAÇÃO", Font(name="Aptos Display", size=16, bold=True, color=WHITE), "brand"),
        (f"{total} produto(s) sem classificação • lojas: {', '.join(stores)}", Font(name="Aptos", size=11, bold=True, color=INK), None),
        ("", None, None),
        ("1. Em cada aba de loja, preencha as colunas laranja GRUPO e SUBCLASSE (há lista suspensa; a subclasse acompanha o grupo).", None, None),
        ("2. Um produto em várias lojas aparece em cada aba, mas é um produto só: preencher em uma aba já vale para todas.", None, None),
        ("3. Salve o arquivo e, no app, abra Explorar estoque › Importar planilha de classificação.", None, None),
        ("4. Linhas com GRUPO ou SUBCLASSE vazios são ignoradas. Pode importar aos poucos.", None, None),
    ]
    for i, (text, font, fill) in enumerate(lines, 1):
        cell = sheet.cell(i, 1, text)
        cell.font = font or Font(name="Aptos", size=11, color=INK)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        if fill == "brand":
            brand_title_row(sheet, i, 1)
        elif fill:
            cell.fill = PatternFill("solid", fgColor=fill)
        sheet.row_dimensions[i].height = 30 if i == 1 else 22


def export_unclassified_xlsx(path, df, catalog=None):
    """Escreve o Excel e retorna quantos produtos únicos foram exportados."""
    rows = unclassified_rows(df)
    products = merge_by_barcode(rows)
    tree = _tree(catalog)

    workbook = Workbook()
    workbook.remove(workbook.active)
    stores = order_stores({s for p in products for s in p["lojas"]})
    _guide_sheet(workbook, len(products), stores)
    used = {"como usar", LISTS_SHEET.casefold()}
    sheets = []
    for store in stores:
        sheet = workbook.create_sheet(_sheet_name(store, used))
        lines = []
        for product in products:
            for entry in product["por_loja"]:
                if entry["loja"] == store:
                    lines.append((product, entry))
        lines.sort(key=lambda pe: barcode_sort_key(pe[0]["codigo_barras"]))
        sheets.append((sheet, store, lines))
    pairs_last, groups_last = _lists_sheet(workbook, tree)

    for sheet, store, lines in sheets:
        sheet.sheet_view.showGridLines = False
        last_col = len(HEADERS)
        letter = get_column_letter(last_col)
        sheet.merge_cells(f"A1:{letter}1")
        sheet["A1"] = f"MIX MODA  •  PRODUTOS SEM CLASSIFICAÇÃO  •  {store}  •  {len(lines)} produto(s)"
        sheet["A1"].font = Font(name="Aptos Display", size=15, bold=True, color=WHITE)
        brand_title_row(sheet, 1, last_col)
        sheet["A1"].alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 30
        sheet.merge_cells(f"A2:{letter}2")
        sheet["A2"] = "Preencha GRUPO e SUBCLASSE (colunas laranja) e importe em Explorar estoque › Importar planilha de classificação."
        sheet["A2"].font = Font(name="Aptos", size=10, italic=True, color=MUTED)

        for c, title in enumerate(HEADERS, 1):
            cell = sheet.cell(HEADER_ROW, c, title)
            fill_me = title in ("GRUPO", "SUBCLASSE")
            cell.font = Font(name="Aptos", size=10, bold=True, color=WHITE)
            cell.fill = PatternFill("solid", fgColor=ORANGE if fill_me else NAVY)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=Side(style="medium", color=BRAND_YELLOW))
        sheet.row_dimensions[HEADER_ROW].height = 30

        for r, (product, entry) in enumerate(lines, HEADER_ROW + 1):
            others = ", ".join(s for s in product["lojas"] if s != store)
            values = [
                str(product["codigo_barras"]), entry["descricao"], store, others or "—",
                entry["quantidade_estoque"], entry["quantidade_vendida"],
                entry["preco_compra"], entry["preco_venda"],
                "", "",  # GRUPO e SUBCLASSE: o cliente preenche
            ]
            for c, value in enumerate(values, 1):
                cell = sheet.cell(r, c, value)
                cell.font = Font(name="Aptos", size=10, color=INK)
                cell.fill = PatternFill("solid", fgColor=FILL_ME if c >= COL["GRUPO"] else (WHITE if r % 2 else PALE))
                cell.alignment = Alignment(horizontal="center" if c in (5, 6, 7, 8) else "left", vertical="center")
                cell.border = Border(bottom=Side(style="hair", color=LINE))
            sheet.cell(r, 1).number_format = "@"
            for c in (COL["Preço de compra"], COL["Preço de venda"]):
                sheet.cell(r, c).number_format = '"R$" #,##0.00'
            sheet.cell(r, COL["Estoque"]).number_format = "0.##"
            sheet.cell(r, COL["Vendas no período"]).number_format = "0.##"
            for c in (COL["GRUPO"], COL["SUBCLASSE"]):
                sheet.cell(r, c).font = Font(name="Aptos", size=10, bold=True, color=INK)

        last_row = HEADER_ROW + len(lines)
        if lines:
            first = HEADER_ROW + 1
            g, s = get_column_letter(COL["GRUPO"]), get_column_letter(COL["SUBCLASSE"])
            sheet.auto_filter.ref = f"A{HEADER_ROW}:{letter}{last_row}"
            sheet.freeze_panes = f"C{first}"
            groups = DataValidation(type="list", formula1=f"{LISTS_SHEET}!$D$2:$D${groups_last}", allow_blank=True)
            groups.errorStyle = "warning"  # aceita grupo novo, só avisa
            groups.error = "Grupo fora da lista do catálogo. Confirme se é um grupo novo."
            groups.showErrorMessage = True
            # Subclasses do grupo escolhido na mesma linha (Listas vem ordenada por grupo).
            subs = DataValidation(
                type="list",
                formula1=(f"OFFSET({LISTS_SHEET}!$B$1,MATCH(${g}{first},{LISTS_SHEET}!$A$2:$A${pairs_last},0),0,"
                          f"MAX(1,COUNTIF({LISTS_SHEET}!$A$2:$A${pairs_last},${g}{first})),1)"),
                allow_blank=True,
            )
            subs.errorStyle = "warning"
            subs.error = "Subclasse fora da lista deste grupo. Confirme se é uma subclasse nova."
            subs.showErrorMessage = True
            for v in (groups, subs):
                sheet.add_data_validation(v)
            groups.add(f"{g}{first}:{g}{last_row}")
            subs.add(f"{s}{first}:{s}{last_row}")
            sheet.conditional_formatting.add(
                f"{g}{first}:{s}{last_row}",
                FormulaRule(formula=[f'AND(${g}{first}<>"",${s}{first}<>"")'],
                            fill=PatternFill("solid", fgColor=GREEN), font=Font(color=GREEN_INK, bold=True)),
            )
        for i, width in enumerate(WIDTHS, 1):
            sheet.column_dimensions[get_column_letter(i)].width = width
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_title_rows = f"1:{HEADER_ROW}"

    if not products:
        sheet = workbook.create_sheet("Sem pendências")
        sheet["A1"] = "Nenhum produto sem classificação nesta análise."
    workbook.save(Path(path))
    return len(products)


class ClassificationFileError(ValueError):
    """O arquivo não tem as colunas mínimas para cadastrar (código, grupo e subclasse)."""


# Nomes de coluna aceitos (sem acento, maiúsculas). Vale para o Excel gerado pelo
# app e para planilhas montadas à mão, com o cabeçalho em qualquer uma das 15 primeiras linhas.
COLUMN_ALIASES = {
    "codigo": ("CODIGO DE BARRAS", "CODIGO BARRAS", "COD BARRAS", "COD. BARRAS", "CODIGO", "COD", "EAN", "GTIN"),
    "descricao": ("DESCRICAO", "DESCRICAO DO PRODUTO", "PRODUTO", "NOME", "NOME DO PRODUTO"),
    "grupo": ("GRUPO",),
    "subclasse": ("SUBCLASSE", "SUB CLASSE", "SUB-CLASSE", "CLASSE"),
    "loja": ("LOJA", "FILIAL", "UNIDADE"),
    "estoque": ("ESTOQUE", "ESTOQUE ATUAL", "QUANTIDADE", "QTD", "QTDE", "SALDO"),
    "preco": ("PRECO DE VENDA", "PRECO VENDA", "PRECO", "VALOR", "VALOR DE VENDA", "PRECO UNITARIO"),
}
_ALIAS_TO_FIELD = {alias: field for field, aliases in COLUMN_ALIASES.items() for alias in aliases}


def _find_header(rows):
    """(número da linha, {campo: coluna}) do primeiro cabeçalho com código, grupo e subclasse."""
    for number, values in enumerate(rows, 1):
        columns = {}
        for i, value in enumerate(values or ()):
            field = _ALIAS_TO_FIELD.get(normalize_text(value))
            if field and field not in columns:
                columns[field] = i
        if {"codigo", "grupo", "subclasse"} <= columns.keys():
            return number, columns
    return None, None


def _sheet_store(title):
    """Nome da aba como loja, quando é uma das lojas da rede (ex.: aba "Palmeiras")."""
    from core.stores import STORES, store_rank
    return STORES[store_rank(title)] if store_rank(title) < len(STORES) else ""


def read_classification_xlsx(path):
    """Lê um Excel de cadastro: o gerado pelo app ou uma planilha com colunas equivalentes.

    Retorna (itens, avisos). Cada item é um produto único (por código) com grupo,
    subclasse e as lojas em que aparece. A loja vem da coluna Loja ou, sem ela, do
    nome da aba. O mesmo código com classificações diferentes vira aviso e fica de fora.
    """
    workbook = load_workbook(Path(path), data_only=True, read_only=True)
    found_sheet = False
    products = {}
    for sheet in workbook.worksheets:
        if sheet.title == LISTS_SHEET:
            continue
        top = list(sheet.iter_rows(min_row=1, max_row=15, values_only=True))
        header_row, cols = _find_header(top)
        if header_row is None:
            continue
        found_sheet = True
        sheet_store = _sheet_store(sheet.title)
        for values in sheet.iter_rows(min_row=header_row + 1, values_only=True):
            def get(field):
                i = cols.get(field)
                return values[i] if i is not None and i < len(values) else None
            raw_code = get("codigo")
            if raw_code is None or not normalize_barcode(raw_code).strip("0"):
                continue
            code = str(int(raw_code)) if isinstance(raw_code, float) and raw_code.is_integer() else str(raw_code).strip()
            item = products.setdefault(normalize_barcode(code), {"codigo_barras": code, "descricao": "", "classes": {}, "lojas": {}})
            descricao = " ".join(str(get("descricao") or "").split())
            item["descricao"] = item["descricao"] or descricao
            loja = str(get("loja") or "").strip() or sheet_store
            if loja:
                item["lojas"].setdefault(normalize_text(loja), {
                    "loja": loja, "descricao": descricao,
                    "quantidade_catalogo": to_number(get("estoque")),
                    "valor": to_number(get("preco")),
                })
            grupo = " ".join(str(get("grupo") or "").split()).upper()
            sub = " ".join(str(get("subclasse") or "").split()).upper()
            if grupo and sub:
                item["classes"].setdefault((grupo, sub), []).append(loja or sheet.title)
    workbook.close()
    if not found_sheet:
        raise ClassificationFileError(
            "Não encontrei as colunas de código de barras, GRUPO e SUBCLASSE em nenhuma aba.\n\n"
            "Use o Excel gerado pelo app ou uma planilha com essas colunas (Descrição, Loja, "
            "Estoque e Preço de venda são opcionais).")
    items, warnings = [], []
    for item in sorted(products.values(), key=lambda p: barcode_sort_key(p["codigo_barras"])):
        classes = item["classes"]
        if not classes:
            continue
        if len(classes) > 1:
            options = "; ".join(f"{g} › {s} ({', '.join(l)})" for (g, s), l in classes.items())
            warnings.append(f"{item['codigo_barras']} – {item['descricao']}: classificações diferentes ({options}).")
            continue
        (grupo, sub), = classes.keys()
        items.append({
            "codigo_barras": item["codigo_barras"], "descricao": item["descricao"],
            "grupo": grupo, "subclasse": sub,
            "lojas": sorted(item["lojas"].values(), key=lambda e: store_sort_key(e["loja"])),
        })
    return items, warnings

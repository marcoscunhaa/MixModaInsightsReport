"""Excel de produtos sem classificação (uma aba por loja) e leitura do Excel preenchido.

Cada aba traz o que é preciso para cadastrar: código, descrição, estoque, preços,
uma sugestão de grupo/subclasse e as colunas GRUPO e SUBCLASSE a preencher (com
lista suspensa). O mesmo arquivo, preenchido, volta para o app em
Explorar estoque › Importar classificações.
"""
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from core.stores import order_stores, store_sort_key
from core.unclassified import AUTO_FILL_SCORE, ClassificationSuggester, is_unclassified, merge_by_barcode, unclassified_rows
from exports.stock_alerts_export import _sheet_name
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
    "Preço de compra", "Preço de venda", "Grupo sugerido", "Subclasse sugerida", "Confiança",
    "GRUPO", "SUBCLASSE",
]
WIDTHS = [20, 42, 17, 26, 10, 11, 13, 13, 24, 24, 11, 26, 26]
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
        ("CADASTRO DE PRODUTOS SEM CLASSIFICAÇÃO", Font(name="Aptos Display", size=16, bold=True, color=WHITE), NAVY),
        (f"{total} produto(s) sem classificação • lojas: {', '.join(stores)}", Font(name="Aptos", size=11, bold=True, color=INK), None),
        ("", None, None),
        ("1. Em cada aba de loja, preencha as colunas laranja GRUPO e SUBCLASSE (há lista suspensa; a subclasse acompanha o grupo).", None, None),
        ("2. Quando a confiança da sugestão é alta, GRUPO e SUBCLASSE já vêm preenchidos: só confira.", None, None),
        ("3. Um produto em várias lojas aparece em cada aba, mas é um produto só: preencher em uma aba já vale para todas.", None, None),
        ("4. Salve o arquivo e, no app, abra Explorar estoque › IMPORTAR CLASSIFICAÇÕES.", None, None),
        ("5. Linhas com GRUPO ou SUBCLASSE vazios são ignoradas. Pode importar aos poucos.", None, None),
    ]
    for i, (text, font, fill) in enumerate(lines, 1):
        cell = sheet.cell(i, 1, text)
        cell.font = font or Font(name="Aptos", size=11, color=INK)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        if fill:
            cell.fill = PatternFill("solid", fgColor=fill)
        sheet.row_dimensions[i].height = 30 if i == 1 else 22


def export_unclassified_xlsx(path, df, catalog=None):
    """Escreve o Excel e retorna quantos produtos únicos foram exportados."""
    rows = unclassified_rows(df)
    products = merge_by_barcode(rows)
    suggester = ClassificationSuggester(catalog)
    tree = _tree(catalog)
    suggestions = {p["codigo_barras"]: suggester.suggest(p["descricao"]) for p in products}

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
        sheet["A1"] = f"PRODUTOS SEM CLASSIFICAÇÃO  •  {store}  •  {len(lines)} produto(s)"
        sheet["A1"].font = Font(name="Aptos Display", size=15, bold=True, color=WHITE)
        sheet["A1"].fill = PatternFill("solid", fgColor=NAVY)
        sheet["A1"].alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 30
        sheet.merge_cells(f"A2:{letter}2")
        sheet["A2"] = "Preencha GRUPO e SUBCLASSE (colunas laranja) e importe em Explorar estoque › Importar classificações."
        sheet["A2"].font = Font(name="Aptos", size=10, italic=True, color=MUTED)

        for c, title in enumerate(HEADERS, 1):
            cell = sheet.cell(HEADER_ROW, c, title)
            fill_me = title in ("GRUPO", "SUBCLASSE")
            cell.font = Font(name="Aptos", size=10, bold=True, color=WHITE)
            cell.fill = PatternFill("solid", fgColor=ORANGE if fill_me else BLUE)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=Side(style="medium", color=NAVY))
        sheet.row_dimensions[HEADER_ROW].height = 30

        for r, (product, entry) in enumerate(lines, HEADER_ROW + 1):
            hint = suggestions.get(product["codigo_barras"])
            auto = hint is not None and hint[2] >= AUTO_FILL_SCORE
            others = ", ".join(s for s in product["lojas"] if s != store)
            values = [
                str(product["codigo_barras"]), entry["descricao"], store, others or "—",
                entry["quantidade_estoque"], entry["quantidade_vendida"],
                entry["preco_compra"], entry["preco_venda"],
                hint[0] if hint else "", hint[1] if hint else "", hint[2] if hint else None,
                hint[0] if auto else "", hint[1] if auto else "",
            ]
            for c, value in enumerate(values, 1):
                cell = sheet.cell(r, c, value)
                cell.font = Font(name="Aptos", size=10, color=INK)
                cell.fill = PatternFill("solid", fgColor=FILL_ME if c >= COL["GRUPO"] else (WHITE if r % 2 else PALE))
                cell.alignment = Alignment(horizontal="center" if c in (5, 6, 7, 8, 11) else "left", vertical="center")
                cell.border = Border(bottom=Side(style="hair", color=LINE))
            sheet.cell(r, 1).number_format = "@"
            for c in (COL["Preço de compra"], COL["Preço de venda"]):
                sheet.cell(r, c).number_format = '"R$" #,##0.00'
            sheet.cell(r, COL["Estoque"]).number_format = "0.##"
            sheet.cell(r, COL["Vendas no período"]).number_format = "0.##"
            sheet.cell(r, COL["Confiança"]).number_format = "0%"
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
    """O arquivo não é o Excel de produtos sem classificação."""


def read_classification_xlsx(path):
    """Lê o Excel preenchido.

    Retorna (itens, avisos). Cada item é um produto único com grupo/subclasse e as
    lojas em que aparece (descrição, estoque e preço de cada aba). O mesmo código
    classificado de formas diferentes em abas diferentes vira aviso e fica de fora.
    """
    workbook = load_workbook(Path(path), data_only=True, read_only=True)
    found_sheet = False
    products = {}
    for sheet in workbook.worksheets:
        if sheet.title == LISTS_SHEET:
            continue
        header = [str(c).strip() if c is not None else "" for c in next(
            sheet.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW, values_only=True), ())]
        if "Código de barras" not in header or "GRUPO" not in header or "SUBCLASSE" not in header:
            continue
        found_sheet = True
        idx = {name: header.index(name) for name in HEADERS if name in header}
        for values in sheet.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
            def get(name):
                i = idx.get(name)
                return values[i] if i is not None and i < len(values) else None
            raw_code = get("Código de barras")
            if raw_code is None or not normalize_barcode(raw_code).strip("0"):
                continue
            code = str(int(raw_code)) if isinstance(raw_code, float) and raw_code.is_integer() else str(raw_code).strip()
            key = normalize_barcode(code)
            item = products.setdefault(key, {"codigo_barras": code, "descricao": "", "classes": {}, "lojas": {}})
            descricao = str(get("Descrição") or "").strip()
            item["descricao"] = item["descricao"] or descricao
            loja = str(get("Loja") or sheet.title).strip()
            item["lojas"].setdefault(normalize_text(loja), {
                "loja": loja, "descricao": descricao,
                "quantidade_catalogo": to_number(get("Estoque")),
                "valor": to_number(get("Preço de venda")),
            })
            grupo = " ".join(str(get("GRUPO") or "").split()).upper()
            sub = " ".join(str(get("SUBCLASSE") or "").split()).upper()
            if grupo and sub:
                item["classes"].setdefault((grupo, sub), []).append(loja)
    workbook.close()
    if not found_sheet:
        raise ClassificationFileError(
            "Este arquivo não tem as colunas GRUPO e SUBCLASSE do Excel de produtos sem classificação.")
    items, warnings = [], []
    for item in sorted(products.values(), key=lambda p: barcode_sort_key(p["codigo_barras"])):
        classes = item["classes"]
        if not classes:
            continue
        if len(classes) > 1:
            options = "; ".join(f"{g} › {s} ({', '.join(l)})" for (g, s), l in classes.items())
            warnings.append(f"{item['codigo_barras']} – {item['descricao']}: classificações diferentes entre lojas ({options}).")
            continue
        (grupo, sub), = classes.keys()
        items.append({
            "codigo_barras": item["codigo_barras"], "descricao": item["descricao"],
            "grupo": grupo, "subclasse": sub,
            "lojas": sorted(item["lojas"].values(), key=lambda e: store_sort_key(e["loja"])),
        })
    return items, warnings

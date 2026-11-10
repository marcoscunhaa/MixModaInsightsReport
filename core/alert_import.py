"""Importação de regras de estoque mínimo a partir da planilha modelo.

A planilha (exports/alert_template_export.py) tem a aba **Alertas**, onde o usuário
cola o código de barras, informa o estoque mínimo e marca as lojas. Aqui lemos essa
aba, conferimos cada linha com o catálogo e com as regras que já existem, e
devolvemos uma prévia; só `apply_import` grava alguma coisa.

Lojas: "Todas as lojas" = Sim, ou nenhuma loja marcada, vale para todas. Marcando
lojas (sem "Todas"), cria uma regra para cada loja marcada, como no formulário.
"""
from dataclasses import dataclass, field

from openpyxl import load_workbook

from core.stores import STORES, store_sort_key
from utils.normalization import barcode_sort_key, normalize_barcode, normalize_text, to_number

SHEET = "Alertas"
HEAD_CODE = "Código de barras"
HEAD_MINIMUM = "Estoque mínimo"
HEAD_ALL = "Todas as lojas"
YES = "Sim"
_TRUTHY = {"SIM", "S", "X", "✓", "✔", "1", "TRUE", "VERDADEIRO", "YES", "OK"}

STATUS_NEW = "nova"
STATUS_UPDATE = "atualiza"
STATUS_SAME = "igual"
STATUS_ERROR = "erro"


def all_stores_label(store):
    return "Todas as lojas" if store == "*" else store


def catalog_by_code(catalog):
    """{código normalizado: produto do catálogo}; o primeiro produto vence se o código repetir."""
    products = {}
    for product in (catalog or {}).get("produtos", []):
        code = normalize_barcode(product.get("codigo_barras"))
        if code and code != "0":
            products.setdefault(code, product)
    return products


def stock_by_code(snapshot):
    """{código normalizado: {loja: estoque}} da última análise."""
    stock = {}
    for row in (snapshot or {}).get("rows", []):
        code = normalize_barcode(row.get("codigo_barras"))
        store = str(row.get("loja", "")).strip()
        if code and store:
            per_store = stock.setdefault(code, {})
            per_store[store] = per_store.get(store, 0.0) + to_number(row.get("quantidade_estoque"))
    return stock


def template_products(catalog, snapshot=None):
    """Produtos da aba Produtos: código, descrição, grupo, subclasse e estoque por loja."""
    stock = stock_by_code(snapshot)
    rows = []
    for code, product in catalog_by_code(catalog).items():
        per_store = {normalize_text(k): v for k, v in stock.get(code, {}).items()}
        rows.append({
            "codigo_barras": str(product.get("codigo_barras", "")).strip() or code,
            "chave": code,
            "descricao": " ".join(str(product.get("descricao", "")).split()),
            "grupo": str(product.get("grupo") or ""),
            "subclasse": str(product.get("subclasse") or ""),
            "estoque": {store: per_store.get(normalize_text(store)) for store in STORES},
        })
    rows.sort(key=lambda r: (normalize_text(r["grupo"]), normalize_text(r["subclasse"]),
                             barcode_sort_key(r["codigo_barras"])))
    return rows


def template_rule_rows(rules):
    """Regras atuais como linhas da aba Alertas (mesmo código e limite = uma linha com várias lojas)."""
    grouped = {}
    for rule in rules or []:
        if not rule.get("ativa", True):
            continue
        code = normalize_barcode(rule.get("codigo_barras"))
        try:
            minimum = int(rule.get("estoque_minimo", 0))
        except (TypeError, ValueError):
            continue
        entry = grouped.setdefault((code, minimum), {"codigo_barras": str(rule.get("codigo_barras", code)),
                                                      "estoque_minimo": minimum, "lojas": set()})
        entry["lojas"].add(str(rule.get("loja", "*")).strip() or "*")
    rows = []
    for entry in grouped.values():
        stores = entry["lojas"]
        if "*" in stores:
            rows.append({**entry, "lojas": ["*"]})
            stores = stores - {"*"}
        if stores:
            rows.append({**entry, "lojas": sorted(stores, key=store_sort_key)})
    rows.sort(key=lambda r: (barcode_sort_key(r["codigo_barras"]), r["lojas"] != ["*"]))
    return rows


@dataclass
class ImportLine:
    linha: int
    codigo_barras: str
    descricao: str = ""
    lojas: list = field(default_factory=list)
    estoque_minimo: int = 0
    status: str = STATUS_NEW
    mensagem: str = ""
    anterior: dict = field(default_factory=dict)  # loja -> mínimo atual

    @property
    def ok(self):
        return self.status != STATUS_ERROR

    @property
    def lojas_texto(self):
        return ", ".join(all_stores_label(s) for s in self.lojas)


@dataclass
class ImportPreview:
    lines: list
    ignored_rows: int = 0

    def count(self, status):
        return sum(1 for line in self.lines if line.status == status)

    @property
    def to_apply(self):
        return [line for line in self.lines if line.status in (STATUS_NEW, STATUS_UPDATE)]

    @property
    def rules_to_write(self):
        return sum(len(line.lojas) for line in self.to_apply)


def _is_yes(value):
    if value is True:
        return True
    return normalize_text(value) in _TRUTHY


def _find_header(sheet):
    for row in sheet.iter_rows(min_row=1, max_row=15):
        for cell in row:
            if normalize_text(cell.value) == normalize_text(HEAD_CODE):
                return cell.row
    return None


def read_rows(path):
    """Linhas preenchidas da aba Alertas: [(linha, código, mínimo, todas, [lojas marcadas])]."""
    workbook = load_workbook(path, read_only=False, data_only=False)
    sheet = workbook[SHEET] if SHEET in workbook.sheetnames else None
    header = None
    if sheet is not None:
        header = _find_header(sheet)
    else:
        for candidate in workbook.worksheets:
            header = _find_header(candidate)
            if header:
                sheet = candidate
                break
    if sheet is None or header is None:
        raise ValueError(f"Não encontrei a aba “{SHEET}” com a coluna “{HEAD_CODE}”. "
                         "Use a planilha modelo baixada pelo app.")
    columns = {}
    for cell in sheet[header]:
        name = normalize_text(cell.value)
        if not name:
            continue
        columns.setdefault(name, cell.column)
    store_columns = {store: columns[normalize_text(store)] for store in STORES if normalize_text(store) in columns}
    code_col = columns[normalize_text(HEAD_CODE)]
    minimum_col = columns.get(normalize_text(HEAD_MINIMUM))
    all_col = columns.get(normalize_text(HEAD_ALL))
    if minimum_col is None:
        raise ValueError(f"A aba “{sheet.title}” não tem a coluna “{HEAD_MINIMUM}”.")

    rows = []
    for row in range(header + 1, sheet.max_row + 1):
        value = lambda col: sheet.cell(row, col).value if col else None
        code, minimum = value(code_col), value(minimum_col)
        marked = [store for store, col in store_columns.items() if _is_yes(value(col))]
        if (code is None or str(code).strip() == "") and (minimum is None or str(minimum).strip() == ""):
            continue
        rows.append((row, code, minimum, _is_yes(value(all_col)), marked))
    return rows


def _minimum(value):
    if value is None or str(value).strip() == "":
        return None, "Informe o estoque mínimo."
    number = to_number(value, default=None)
    if number is None:
        return None, f"Estoque mínimo inválido: “{value}”."
    if number < 0:
        return None, "O estoque mínimo precisa ser zero ou mais."
    if abs(number - round(number)) > 1e-9:
        return None, "Use um número inteiro de unidades no estoque mínimo."
    return int(round(number)), ""


def build_preview(rows, catalog, rules):
    """Confere as linhas lidas com o catálogo e as regras atuais (não grava nada)."""
    products = catalog_by_code(catalog)
    current = {}
    for rule in rules or []:
        key = (normalize_barcode(rule.get("codigo_barras")), normalize_text(rule.get("loja", "*")))
        current[key] = rule
    lines, seen = [], {}
    for row, code_value, minimum_value, all_stores, marked in rows:
        code = normalize_barcode(code_value)
        shown = str(code_value).strip() if code_value is not None else ""
        if isinstance(code_value, float) and code_value.is_integer():
            shown = str(int(code_value))
        line = ImportLine(row, shown)
        line.lojas = ["*"] if all_stores or not marked else sorted(marked, key=store_sort_key)
        if not code or code == "0":
            line.status, line.mensagem = STATUS_ERROR, "Falta o código de barras."
            lines.append(line)
            continue
        product = products.get(code)
        if product is None:
            line.status, line.mensagem = STATUS_ERROR, "Código não está no catálogo."
            lines.append(line)
            continue
        line.codigo_barras = str(product.get("codigo_barras", shown)).strip() or shown
        line.descricao = " ".join(str(product.get("descricao", "")).split())
        minimum, problem = _minimum(minimum_value)
        if problem:
            line.status, line.mensagem = STATUS_ERROR, problem
            lines.append(line)
            continue
        line.estoque_minimo = minimum
        # Código e loja repetidos: vale a última linha da planilha.
        for store in line.lojas:
            earlier = seen.get((code, normalize_text(store)))
            if earlier is not None and earlier is not line:
                earlier.lojas = [s for s in earlier.lojas if normalize_text(s) != normalize_text(store)]
                if not earlier.lojas:
                    earlier.status, earlier.mensagem = STATUS_SAME, f"Repetido: vale a linha {row}."
            seen[(code, normalize_text(store))] = line
        lines.append(line)

    for line in lines:
        if line.status == STATUS_ERROR or not line.lojas:
            continue
        code = normalize_barcode(line.codigo_barras)
        for store in line.lojas:
            rule = current.get((code, normalize_text(store)))
            if rule is not None:
                line.anterior[store] = int(rule.get("estoque_minimo", 0))
        if not line.anterior:
            line.status = STATUS_NEW
        elif len(line.anterior) == len(line.lojas) and all(v == line.estoque_minimo for v in line.anterior.values()):
            line.status, line.mensagem = STATUS_SAME, "Já existe com o mesmo limite."
        else:
            line.status = STATUS_UPDATE
            before = sorted(set(line.anterior.values()))
            news = len(line.lojas) - len(line.anterior)
            line.mensagem = (f"Limite atual: {', '.join(str(v) for v in before)} → {line.estoque_minimo}"
                             + (f"  •  +{news} loja(s) nova(s)" if news else ""))
    return ImportPreview(lines)


def preview_file(path, catalog, rules):
    return build_preview(read_rows(path), catalog, rules)


def apply_import(preview, alert_store):
    """Grava as linhas novas e as que mudaram; devolve quantas regras foram salvas."""
    # A regra salva antes pode ter outra descrição: atualiza essa mesma regra em vez de duplicar.
    existing = {(normalize_barcode(r.get("codigo_barras")), normalize_text(r.get("loja", "*"))): r
                for r in alert_store.load_rules()}
    saved = 0
    for line in preview.to_apply:
        for store in line.lojas:
            rule = existing.get((normalize_barcode(line.codigo_barras), normalize_text(store)))
            alert_store.upsert_rule({
                "codigo_barras": rule.get("codigo_barras") if rule else line.codigo_barras,
                "descricao": rule.get("descricao") if rule else line.descricao,
                "loja": store,
                "estoque_minimo": line.estoque_minimo,
            })
            saved += 1
    return saved

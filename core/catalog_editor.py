"""CRUD for the official catalog (catalogo_produtos_estoque_geral.json).

Each product has general data (barcode, description, group, subclass, status)
and a `lojas[]` (stores) list with quantity, price and the description used in
that store. Sales matching uses store + barcode + description, so each store's
description is preserved when it differs from the general one.

This module does not depend on Qt: the stock screen only calls these functions.
"""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from core.stores import STORES
from utils.normalization import normalize_barcode, normalize_text

ACTIVE = "ACTIVE"
SITUACOES = (ACTIVE, "INACTIVE")


class CatalogValidationError(ValueError):
    """Invalid form data; the message is shown to the user."""


def clean_label(value):
    """Collapse extra whitespace. Upper case is applied by the form while typing,
    so legacy text the user did not touch is not rewritten."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_number(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def format_quantity(value):
    return str(int(round(parse_number(value))))


def format_price(value):
    return f"{parse_number(value):.2f}"


def product_stock(product):
    return sum(parse_number(l.get("quantidade_catalogo")) for l in product.get("lojas", []))


def store_names(catalog):
    """The chain's stores (core.stores), using the spelling already in the catalog.

    The catalog stores "pedras" in lower case; reusing the existing spelling avoids
    two versions of the same store in the JSON. Catalog-only stores come last.
    """
    in_catalog = list(catalog.get("meta", {}).get("lojas", []))
    for product in catalog.get("produtos", []):
        for entry in product.get("lojas", []):
            in_catalog.append(entry.get("loja", ""))
    spelling = {}
    for name in in_catalog:
        if name:
            spelling.setdefault(normalize_text(name), name)
    names = [spelling.get(normalize_text(store), store) for store in STORES]
    official = {normalize_text(store) for store in STORES}
    names += [name for key, name in spelling.items() if key not in official]
    return names


def groups_and_subclasses(catalog):
    """Sorted {group: [subclasses]} used to fill the form combo boxes."""
    tree = {}
    for product in catalog.get("produtos", []):
        tree.setdefault(product.get("grupo", ""), set()).add(product.get("subclasse", ""))
    return {
        g: sorted((s for s in subs if s), key=normalize_text)
        for g, subs in sorted(tree.items(), key=lambda kv: normalize_text(kv[0]))
        if g
    }


def find_product(catalog, codigo_barras):
    """Look up by exact barcode: the legacy catalog has pairs that differ only by leading zeros."""
    code = str(codigo_barras).strip()
    for product in catalog.get("produtos", []):
        if str(product.get("codigo_barras")).strip() == code:
            return product
    return None


def _same_code_product(catalog, code, ignore=None):
    """Another product whose barcode is the same number (ignoring leading zeros)."""
    key = normalize_barcode(code)
    for product in catalog.get("produtos", []):
        if product is not ignore and normalize_barcode(product.get("codigo_barras")) == key:
            return product
    return None


def _validate(catalog, data, original_code=None):
    code = re.sub(r"\s+", "", str(data.get("codigo_barras", "")))
    if not code:
        raise CatalogValidationError("Enter the barcode.")
    if not code.isdigit():
        raise CatalogValidationError("The barcode must contain only numbers.")
    descricao = clean_label(data.get("descricao"))
    grupo = clean_label(data.get("grupo"))
    subclasse = clean_label(data.get("subclasse"))
    situacao = clean_label(data.get("situacao") or ACTIVE).upper()
    if not descricao:
        raise CatalogValidationError("Enter the product description.")
    if not grupo:
        raise CatalogValidationError("Enter the group.")
    if not subclasse:
        raise CatalogValidationError("Enter the subclass.")
    if situacao not in SITUACOES:
        raise CatalogValidationError("Status must be ACTIVE or INACTIVE.")

    original = find_product(catalog, original_code) if original_code is not None else None
    changed_number = original is None or normalize_barcode(code) != normalize_barcode(original_code)
    existing = _same_code_product(catalog, code, ignore=original) if changed_number else None
    if existing is not None:
        raise CatalogValidationError(
            f"A product with barcode {existing['codigo_barras']} already exists: {existing['descricao']}."
        )

    lojas = []
    seen = set()
    for entry in data.get("lojas", []):
        loja = str(entry.get("loja", "")).strip()
        if not loja:
            raise CatalogValidationError("Select the store on every row.")
        if normalize_text(loja) in seen:
            raise CatalogValidationError(f"Store {loja} appears more than once.")
        seen.add(normalize_text(loja))
        quantidade = parse_number(entry.get("quantidade_catalogo"))
        valor = parse_number(entry.get("valor"))
        # Negative quantities happen in real stock (sold without a receipt); negative prices do not.
        if valor < 0:
            raise CatalogValidationError(f"The price cannot be negative ({loja}).")
        lojas.append({
            "loja": loja,
            "descricao": clean_label(entry.get("descricao")) or descricao,
            "quantidade_catalogo": quantidade,
            "valor": valor,
        })
    if not lojas:
        raise CatalogValidationError("Select at least one store.")
    return {
        "codigo_barras": code,
        "descricao": descricao,
        "grupo": grupo,
        "subclasse": subclasse,
        "situacao": situacao,
        "lojas": lojas,
    }


def _store_entry(clean, store, previous=None):
    """Build a lojas[] entry with the same key order as the original file.

    Numerically equal quantity and price keep the previous text, so the JSON diff
    shows only what actually changed.
    """
    previous = previous or {}
    qty = previous.get("quantidade_catalogo")
    if qty is None or parse_number(qty) != store["quantidade_catalogo"]:
        qty = format_quantity(store["quantidade_catalogo"])
    price = previous.get("valor")
    if price is None or round(parse_number(price), 2) != round(store["valor"], 2):
        price = format_price(store["valor"])
    return {
        "loja": store["loja"],
        "situacao": clean["situacao"],
        "grupo": clean["grupo"],
        "subclasse": clean["subclasse"],
        "descricao": store["descricao"],
        "quantidade_catalogo": qty,
        "valor": price,
        "codigo_barras": normalize_barcode(clean["codigo_barras"]),
        "descricao_norm": normalize_text(store["descricao"]),
    }


def _build_product(clean, previous=None):
    old_stores = {normalize_text(l["loja"]): l for l in (previous or {}).get("lojas", [])}
    return {
        "codigo_barras": clean["codigo_barras"],
        "grupo": clean["grupo"],
        "subclasse": clean["subclasse"],
        "descricao": clean["descricao"],
        "situacao": clean["situacao"],
        "lojas": [
            _store_entry(clean, store, old_stores.get(normalize_text(store["loja"])))
            for store in clean["lojas"]
        ],
    }


def refresh_meta(catalog):
    """Recompute the meta totals with the same rules as the generated file."""
    products = catalog.get("produtos", [])
    entries = [l for p in products for l in p.get("lojas", [])]
    meta = catalog.setdefault("meta", {})
    meta["total_linhas"] = len(entries)
    meta["total_produtos_unicos_por_codigo"] = len(products)
    meta["total_grupos"] = len({p.get("grupo") for p in products})
    meta["total_subclasses"] = len({p.get("subclasse") for p in products})
    lojas = list(meta.get("lojas", []))
    known = {normalize_text(n) for n in lojas}
    for entry in entries:
        if normalize_text(entry.get("loja")) not in known:
            known.add(normalize_text(entry.get("loja")))
            lojas.append(entry.get("loja"))
    meta["lojas"] = lojas
    classificacao = meta.setdefault("classificacao", {})
    classificacao["total_registros"] = len(entries)
    classificacao["total_grupos"] = len({l.get("grupo") for l in entries})
    classificacao["total_subclasses"] = len({(l.get("grupo"), l.get("subclasse")) for l in entries})
    return catalog


def add_product(catalog, data):
    clean = _validate(catalog, data)
    product = _build_product(clean)
    catalog.setdefault("produtos", []).append(product)
    refresh_meta(catalog)
    return product


def update_product(catalog, original_code, data):
    products = catalog.get("produtos", [])
    previous = find_product(catalog, original_code)
    if previous is None:
        raise CatalogValidationError("Product not found; it may have been removed.")
    clean = _validate(catalog, data, original_code=original_code)
    index = next(i for i, p in enumerate(products) if p is previous)
    # Stores whose description matched the general one follow the new description.
    old_description = normalize_text(previous.get("descricao"))
    if normalize_text(clean["descricao"]) != old_description:
        for store in clean["lojas"]:
            if normalize_text(store["descricao"]) == old_description:
                store["descricao"] = clean["descricao"]
    products[index] = _build_product(clean, previous)
    refresh_meta(catalog)
    return products[index]


def delete_product(catalog, codigo_barras):
    products = catalog.get("produtos", [])
    target = find_product(catalog, codigo_barras)
    remaining = [p for p in products if p is not target]
    if target is None:
        raise CatalogValidationError("Product not found; it may already have been removed.")
    catalog["produtos"] = remaining
    refresh_meta(catalog)


def save_catalog(catalog, path, keep_backup=True):
    """Write atomically, in the same format as the file (indent 2, UTF-8).

    The previous version is kept in `<file>.bak` to undo a mistake by hand.
    """
    path = Path(path)
    payload = json.dumps(catalog, ensure_ascii=False, indent=2)
    if keep_backup and path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".catalogo-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def editable_catalog_path(bundled_path, data_dir):
    """Writable path of the catalog.

    When running from source, the catalog already lives in data/ and is edited in place.
    In the executable, the bundled JSON is read-only: on first run it is copied to
    the user's data folder and edits go to that copy.
    """
    bundled = Path(bundled_path)
    target = Path(data_dir) / bundled.name
    if target.resolve() == bundled.resolve():
        return bundled
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)
    return target


# ---------- corrupted catalog ----------

class CatalogFileError(ValueError):
    """The catalog file cannot be used; the message explains why."""


def check_catalog(path):
    """Read and validate the minimal catalog structure. Returns the catalog or raises CatalogFileError."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            catalog = json.load(f)
    except FileNotFoundError:
        raise CatalogFileError(f"The file {path.name} was not found.") from None
    except json.JSONDecodeError as error:
        raise CatalogFileError(
            f"The file {path.name} has invalid JSON "
            f"(line {error.lineno}, column {error.colno}: {error.msg})."
        ) from None
    except (OSError, UnicodeDecodeError) as error:
        raise CatalogFileError(f"Could not read {path.name}: {error}") from None
    if not isinstance(catalog, dict) or not isinstance(catalog.get("produtos"), list):
        raise CatalogFileError(f"The file {path.name} does not contain the catalog product list.")
    for index, product in enumerate(catalog["produtos"], start=1):
        if (
            not isinstance(product, dict)
            or not str(product.get("codigo_barras", "")).strip()
            or not isinstance(product.get("lojas"), list)
        ):
            raise CatalogFileError(
                f"Product #{index} in {path.name} is incomplete "
                "(missing barcode or store list)."
            )
    return catalog


def recovery_sources(path, bundled_path=None):
    """Valid copies to restore from, in order of preference: backup, then bundled catalog."""
    path = Path(path)
    options = [("backup of the last change", path.with_name(path.name + ".bak"))]
    if bundled_path and Path(bundled_path).resolve() != path.resolve():
        options.append(("original catalog bundled with the app", Path(bundled_path)))
    valid = []
    for label, source in options:
        try:
            check_catalog(source)
        except CatalogFileError:
            continue
        valid.append((label, source))
    return valid


def restore_catalog(path, source):
    """Replace the invalid catalog with the `source` copy, keeping the invalid file.

    The broken file is never deleted: it becomes `<name>.corrupted-<date-time>.json`
    in the same folder, for review. Returns the path where it was kept.
    """
    from datetime import datetime

    path = Path(path)
    kept = None
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        kept = path.with_name(f"{path.stem}.corrupted-{stamp}{path.suffix}")
        shutil.copy2(path, kept)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".catalogo-", suffix=".json")
    os.close(fd)
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return kept

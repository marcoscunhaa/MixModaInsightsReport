from pathlib import Path
import pandas as pd
from utils.normalization import normalize_barcode, normalize_text, to_number

# Actual layout of Mix Moda's spreadsheet exports.
# Stock: A barcode, B description, D quantity, E purchase price, F current sale price.
STOCK_MAP = {"codigo_barras": 0, "descricao": 1, "quantidade_estoque": 3, "preco_compra": 4, "preco_venda": 5}
# Sales: A barcode, B description, C quantity sold, D purchase price,
# E total cost, F sale price, G revenue (C × F), H profit.
SALES_MAP = {
    "codigo_barras": 0, "descricao": 1, "quantidade_vendida": 2,
    "preco_compra": 3, "preco_venda": 5, "faturamento": 6,
}
# Older sales exports only have A–C; missing prices become 0 and the matching
# falls back to the sale price from the stock spreadsheet (column F).
SALES_REQUIRED = ("codigo_barras", "descricao", "quantidade_vendida")


def _looks_like_html(path):
    try:
        with open(path, "rb") as f:
            head = f.read(4096).lower()
        return b"<html" in head or b"<table" in head or b"<!doctype" in head
    except Exception:
        return False


def _read_html_report(path):
    tables = pd.read_html(path, header=None)
    if not tables:
        raise ValueError("No HTML table was found in the file.")
    return max(tables, key=lambda t: (t.shape[0] * max(t.shape[1], 1), t.shape[1]))


def read_raw(path):
    path = Path(path)
    suffix = path.suffix.lower()
    errors = []
    if suffix == ".xls" and _looks_like_html(path):
        try:
            return _read_html_report(path)
        except Exception as e:
            errors.append(f"HTML: {e}")
    engines = ["xlrd"] if suffix == ".xls" else ["openpyxl"]
    for engine in engines:
        try:
            return pd.read_excel(path, header=None, engine=engine)
        except Exception as e:
            errors.append(f"{engine}: {e}")
    if suffix == ".xls":
        try:
            return _read_html_report(path)
        except Exception as e:
            errors.append(f"HTML fallback: {e}")
    msg = "Could not read the spreadsheet."
    if errors:
        msg += " Attempts: " + " | ".join(errors)
    raise ValueError(msg)


def _standardize(raw, mapping, required=None):
    required = set(required or mapping)
    required_columns = max(i for k, i in mapping.items() if k in required) + 1
    if raw.shape[1] < required_columns:
        raise ValueError(
            f"Spreadsheet has {raw.shape[1]} columns; the expected layout needs at least {required_columns}."
        )
    out = {k: (raw.iloc[:, i] if i < raw.shape[1] else pd.Series(index=raw.index, dtype=float)) for k, i in mapping.items()}
    df = pd.DataFrame(out).dropna(how="all").copy()
    if len(df):
        # Skip a header row (the source headers are in Portuguese).
        desc0 = normalize_text(df.iloc[0].get("descricao", ""))
        if desc0 in {"DESCRICAO", "PRODUTO", "DESCRICAO DO PRODUTO"}:
            df = df.iloc[1:].copy()
    df["codigo_barras"] = df["codigo_barras"].map(normalize_barcode)
    df["descricao"] = df["descricao"].map(normalize_text)
    for c in df.columns:
        if c not in {"codigo_barras", "descricao"}:
            df[c] = df[c].map(to_number)
    return df.reset_index(drop=True)


def _column_c_text_share(raw):
    """Share of text values in column C: "UN" (unit) in stock, a quantity in sales."""
    if raw.shape[1] < 3:
        return None
    values = raw.iloc[:, 2].dropna()
    values = values[values.map(lambda v: str(v).strip() != "")]
    if len(values) < 5:
        return None
    return values.map(lambda v: isinstance(v, str) and not str(v).strip().replace(",", ".").replace(".", "", 1).isdigit()).mean()


def load_stock(path):
    raw = read_raw(path)
    share = _column_c_text_share(raw)
    if share is not None and share < 0.5:
        raise ValueError(
            f"The file {Path(path).name} looks like a SALES spreadsheet (column C holds quantities). "
            "Check that the stock and sales files were not swapped."
        )
    return _standardize(raw, STOCK_MAP)


def load_sales(path):
    raw = read_raw(path)
    share = _column_c_text_share(raw)
    if share is not None and share > 0.5:
        raise ValueError(
            f"The file {Path(path).name} looks like a STOCK spreadsheet (column C holds the unit, e.g. UN). "
            "Check that the stock and sales files were not swapped."
        )
    return _standardize(raw, SALES_MAP, SALES_REQUIRED)

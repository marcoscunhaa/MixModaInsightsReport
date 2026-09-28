from pathlib import Path
import pandas as pd
from utils.normalization import normalize_barcode, normalize_text, to_number

# Layout real das extrações Mix Moda.
STOCK_MAP = {"codigo_barras": 0, "descricao": 1, "quantidade_estoque": 3, "preco_compra": 4, "preco_venda": 6}
SALES_MAP = {"codigo_barras": 0, "descricao": 1, "quantidade_vendida": 2}


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
        raise ValueError("Nenhuma tabela HTML foi encontrada no arquivo.")
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
    msg = "Não foi possível ler a planilha."
    if errors:
        msg += " Tentativas: " + " | ".join(errors)
    raise ValueError(msg)


def _standardize(raw, mapping):
    out = {k: (raw.iloc[:, i] if i < raw.shape[1] else pd.Series(index=raw.index)) for k, i in mapping.items()}
    df = pd.DataFrame(out).dropna(how="all").copy()
    if len(df):
        desc0 = normalize_text(df.iloc[0].get("descricao", ""))
        if desc0 in {"DESCRICAO", "PRODUTO", "DESCRICAO DO PRODUTO"}:
            df = df.iloc[1:].copy()
    df["codigo_barras"] = df["codigo_barras"].map(normalize_barcode)
    df["descricao"] = df["descricao"].map(normalize_text)
    for c in df.columns:
        if c not in {"codigo_barras", "descricao"}:
            df[c] = df[c].map(to_number)
    return df.reset_index(drop=True)


def load_stock(path):
    return _standardize(read_raw(path), STOCK_MAP)


def load_sales(path):
    return _standardize(read_raw(path), SALES_MAP)

from pathlib import Path
import pandas as pd
from utils.normalization import normalize_barcode, normalize_text, to_number

# Layout real das extrações Mix Moda.
# Estoque: A código, B descrição, D quantidade, E preço de compra, F preço de venda atual.
STOCK_MAP = {"codigo_barras": 0, "descricao": 1, "quantidade_estoque": 3, "preco_compra": 4, "preco_venda": 5}
# Vendas: A código, B descrição, C quantidade vendida, D preço de compra,
# E custo total, F preço de venda, G faturamento (C × F), H lucro.
SALES_MAP = {
    "codigo_barras": 0, "descricao": 1, "quantidade_vendida": 2,
    "preco_compra": 3, "preco_venda": 5, "faturamento": 6,
}
# Extrações antigas de vendas têm só A–C; os preços ausentes viram 0 e o
# cruzamento usa o preço de venda da planilha de estoque (coluna F).
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


def _standardize(raw, mapping, required=None):
    required = set(required or mapping)
    required_columns = max(i for k, i in mapping.items() if k in required) + 1
    if raw.shape[1] < required_columns:
        raise ValueError(
            f"Planilha com {raw.shape[1]} colunas; o layout esperado precisa de pelo menos {required_columns}."
        )
    out = {k: (raw.iloc[:, i] if i < raw.shape[1] else pd.Series(index=raw.index, dtype=float)) for k, i in mapping.items()}
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


def _column_c_text_share(raw):
    """Fração de textos na coluna C: "UN" no estoque, quantidade nas vendas."""
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
            f"O arquivo {Path(path).name} parece ser uma planilha de VENDAS (coluna C com quantidades). "
            "Confira se os arquivos de estoque e de vendas não foram trocados."
        )
    return _standardize(raw, STOCK_MAP)


def load_sales(path):
    raw = read_raw(path)
    share = _column_c_text_share(raw)
    if share is not None and share > 0.5:
        raise ValueError(
            f"O arquivo {Path(path).name} parece ser uma planilha de ESTOQUE (coluna C com a unidade, ex.: UN). "
            "Confira se os arquivos de estoque e de vendas não foram trocados."
        )
    return _standardize(raw, SALES_MAP, SALES_REQUIRED)

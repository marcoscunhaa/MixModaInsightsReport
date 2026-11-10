"""Estoque completo: uma linha por produto × loja com o preço de venda a usar.

Base do Excel "Estoque completo" (exports/inventory_export.py). Não depende de Qt.

Preço de venda, na ordem:
1. **Sistema** – o preço definido na planilha de estoque (coluna F).
2. **Vendas do período** – sem preço no sistema, o valor registrado nas vendas.
3. **Catálogo** – o último valor gravado no catálogo para aquela loja.
4. **Estimado** – 2× o preço de compra (a mesma regra da análise quando nada existe).
"""
import math

import pandas as pd

from core.stores import store_sort_key
from core.unclassified import is_unclassified
from utils.normalization import barcode_sort_key, normalize_barcode, normalize_text, to_number

PRICE_SYSTEM = "Sistema"
PRICE_SALES = "Vendas do período"
PRICE_CATALOG = "Catálogo"
PRICE_ESTIMATED = "Estimado (2× compra)"
PRICE_NONE = "Sem preço"

COLUMNS = [
    "codigo_barras", "loja", "descricao", "grupo", "subclasse",
    "estoque", "preco_venda", "valor_total", "origem_preco", "status",
]


def _num(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if isinstance(value, float) and math.isnan(value) else float(value)
    return to_number(value)


def catalog_prices(catalog):
    """{(código normalizado, loja normalizada): último valor de venda do catálogo}."""
    prices = {}
    for product in (catalog or {}).get("produtos", []):
        code = normalize_barcode(product.get("codigo_barras"))
        for entry in product.get("lojas", []) or []:
            value = _num(entry.get("valor"))
            if value > 0:
                prices[(code, normalize_text(entry.get("loja")))] = value
    return prices


def sale_price(row, catalog_lookup=None, has_system_column=True):
    """(preço, origem) de uma linha da análise, seguindo a ordem do módulo."""
    system = _num(row.get("preco_venda_sistema")) if has_system_column else 0.0
    if system > 0:
        return system, PRICE_SYSTEM
    current = _num(row.get("preco_venda_atual"))  # coluna F quando houve vários preços
    if current > 0:
        return current, PRICE_SYSTEM
    price = _num(row.get("preco_venda"))
    if _num(row.get("quantidade_vendida")) > 0 and price > 0:
        return price, PRICE_SALES
    # Análises salvas antes desta versão não guardam a coluna F à parte: sem venda,
    # o preço da análise já é a coluna F, a não ser que seja a estimativa de 2×.
    cost = _num(row.get("preco_compra_estoque", row.get("preco_compra")))
    estimated = cost > 0 and abs(price - 2 * cost) < 0.005
    if not has_system_column and price > 0 and not estimated:
        return price, PRICE_SYSTEM
    key = (normalize_barcode(row.get("codigo_barras")), normalize_text(row.get("loja")))
    catalog_value = (catalog_lookup or {}).get(key, 0.0)
    if catalog_value > 0:
        return catalog_value, PRICE_CATALOG
    if price > 0:
        return price, PRICE_ESTIMATED
    return 0.0, PRICE_NONE


def _group_key(value):
    # "SEM CLASSIFICAÇÃO" vai para o fim; o resto em ordem alfabética.
    return (1 if is_unclassified(value) else 0, normalize_text(value))


def inventory_rows(df, catalog=None):
    """DataFrame com as colunas de COLUMNS, ordenado por grupo › subclasse › código › loja."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)
    lookup = catalog_prices(catalog)
    has_system = "preco_venda_sistema" in df.columns
    rows = []
    for record in df.to_dict("records"):
        price, origin = sale_price(record, lookup, has_system)
        stock = _num(record.get("quantidade_estoque"))
        rows.append({
            "codigo_barras": str(record.get("codigo_barras", "")),
            "loja": str(record.get("loja", "")),
            "descricao": " ".join(str(record.get("descricao", "")).split()),
            "grupo": str(record.get("grupo") or "SEM CLASSIFICAÇÃO"),
            "subclasse": str(record.get("subclasse") or "SEM CLASSIFICAÇÃO"),
            "estoque": stock,
            "preco_venda": round(price, 2),
            # Estoque negativo não vira valor negativo: é falta de entrada no sistema.
            "valor_total": round(max(stock, 0.0) * price, 2),
            "origem_preco": origin,
            "status": str(record.get("status_estoque", "") or ""),
        })
    rows.sort(key=lambda r: (_group_key(r["grupo"]), _group_key(r["subclasse"]),
                             barcode_sort_key(r["codigo_barras"]), store_sort_key(r["loja"])))
    return pd.DataFrame(rows, columns=COLUMNS)

"""Produtos sem classificação: um produto por código, sugestão e cadastro em lote.

O mesmo código de barras aparece uma vez por loja na análise. Para quem vai
cadastrar, isso é um produto só: aqui ele vira uma linha com as lojas em que
está, e o explorador e o Excel contam esse produto uma única vez.

Também sugere grupo/subclasse a partir dos produtos já classificados no
catálogo (descrição parecida) e aplica de volta no catálogo o que foi
preenchido no Excel. Não depende de Qt.
"""
import difflib
from collections import Counter

import pandas as pd

from core.stores import order_stores, store_sort_key
from utils.normalization import barcode_sort_key, normalize_barcode, normalize_text

UNCLASSIFIED = "SEM CLASSIFICAÇÃO"

# Mesma prioridade dos produtos críticos: o status mais grave entre as lojas vale para o produto.
_STATUS_SEVERITY = ["NEGATIVO", "SEM ESTOQUE", "CRÍTICO", "BAIXO", "SEM VENDA", "EXCESSO", "NORMAL"]

# Pontuação mínima para o Excel já trazer a sugestão nas colunas a preencher.
AUTO_FILL_SCORE = 0.80


def is_unclassified(value):
    return normalize_text(value) == normalize_text(UNCLASSIFIED)


def unclassified_rows(df):
    """Linhas (produto × loja) sem grupo ou sem subclasse."""
    if df.empty:
        return df
    mask = df.grupo.map(is_unclassified) | df.subclasse.map(is_unclassified)
    return df[mask]


def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return value if value == value else 0.0


def merge_by_barcode(df):
    """Um registro por código de barras, somando as lojas.

    Cada registro traz `lojas` (ordem oficial) e `por_loja` com estoque, vendas
    e descrição de cada loja; `loja` vira o texto "Loja A, Loja B" para o card.
    """
    if df.empty:
        return []
    out = []
    keys = df.codigo_barras.map(normalize_barcode)
    for _code, part in df.groupby(keys, sort=False):
        part = part.copy()
        part["_ordem"] = part.loja.map(store_sort_key)
        part = part.sort_values("_ordem", kind="stable")
        first = part.iloc[0].to_dict()
        first.pop("_ordem", None)
        stores = order_stores(part.loja.dropna().astype(str).unique())
        estoque = float(part.quantidade_estoque.map(_num).sum())
        vendas = float(part.quantidade_vendida.map(_num).sum())
        faturamento = float(part.valor_vendido.map(_num).sum()) if "valor_vendido" in part else 0.0
        valor_estoque = float(part.valor_estoque.map(_num).sum()) if "valor_estoque" in part else 0.0
        compra = part.preco_compra.map(_num) if "preco_compra" in part else pd.Series([0.0])
        venda = part.preco_venda.map(_num) if "preco_venda" in part else pd.Series([0.0])
        preco_compra = float(compra[compra > 0].mean()) if (compra > 0).any() else 0.0
        preco_venda = faturamento / vendas if vendas > 0 and faturamento > 0 else (
            float(venda[venda > 0].mean()) if (venda > 0).any() else 0.0)
        statuses = [str(s) for s in part.get("status_estoque", pd.Series(dtype=str)).dropna()]
        status = min(statuses, key=lambda s: _STATUS_SEVERITY.index(s) if s in _STATUS_SEVERITY else 99) if statuses else "—"
        descricao = Counter(part.descricao.astype(str)).most_common(1)[0][0]
        first.update({
            "codigo_barras": str(first.get("codigo_barras", "")),
            "descricao": descricao,
            "loja": ", ".join(stores),
            "lojas": stores,
            "quantidade_estoque": estoque,
            "quantidade_vendida": vendas,
            "valor_vendido": faturamento,
            "valor_estoque": valor_estoque,
            "preco_compra": preco_compra,
            "preco_venda": preco_venda,
            "margem_unitaria": preco_venda - preco_compra,
            "margem_percentual": (preco_venda - preco_compra) / preco_venda * 100 if preco_venda else 0.0,
            "giro": vendas / (vendas + estoque) * 100 if (vendas + estoque) > 0 else 0.0,
            "status_estoque": status,
            # Vários preços por loja não somam entre lojas: o card mostra os totais.
            "precos_venda": [],
            "preco_venda_atual": None,
            "por_loja": [
                {
                    "loja": str(r.loja),
                    "descricao": str(r.descricao),
                    "quantidade_estoque": _num(r.quantidade_estoque),
                    "quantidade_vendida": _num(r.quantidade_vendida),
                    "preco_compra": _num(getattr(r, "preco_compra", 0)),
                    "preco_venda": _num(getattr(r, "preco_venda", 0)),
                    "status_estoque": str(getattr(r, "status_estoque", "")),
                }
                for r in part.itertuples(index=False)
            ],
        })
        out.append(first)
    return sorted(out, key=lambda r: barcode_sort_key(r["codigo_barras"]))


def product_count(df):
    """Quantos produtos há em `df`: os sem classificação contam uma vez por código."""
    if df.empty:
        return 0
    loose = unclassified_rows(df)
    classified = len(df) - len(loose)
    return int(classified + loose.codigo_barras.map(normalize_barcode).nunique())


# ---------- sugestão de classificação ----------

def _tokens(text):
    return [w for w in normalize_text(text).replace("/", " ").replace("-", " ").split() if len(w) > 1 and not w.isdigit()]


class ClassificationSuggester:
    """Sugere grupo/subclasse pela descrição mais parecida entre os produtos já classificados."""

    def __init__(self, catalog):
        self.entries = []
        self.by_token = {}
        seen = set()
        for product in (catalog or {}).get("produtos", []):
            grupo, sub = product.get("grupo", ""), product.get("subclasse", "")
            if not grupo or not sub or is_unclassified(grupo) or is_unclassified(sub):
                continue
            descricoes = {product.get("descricao", "")} | {l.get("descricao", "") for l in product.get("lojas", [])}
            for desc in descricoes:
                norm = normalize_text(desc)
                if not norm or (norm, grupo, sub) in seen:
                    continue
                seen.add((norm, grupo, sub))
                index = len(self.entries)
                self.entries.append((norm, grupo, sub, desc))
                for token in set(_tokens(norm)):
                    self.by_token.setdefault(token, []).append(index)

    def suggest(self, descricao):
        """(grupo, subclasse, pontuação 0–1, descrição de referência) ou None."""
        norm = normalize_text(descricao)
        tokens = _tokens(norm)
        if not norm or not tokens:
            return None
        candidates = set()
        for token in tokens:
            candidates.update(self.by_token.get(token, ()))
        if not candidates:
            return None
        best = None
        for index in candidates:
            ref, grupo, sub, original = self.entries[index]
            ratio = difflib.SequenceMatcher(None, norm, ref).ratio()
            ref_tokens = set(_tokens(ref))
            # A primeira palavra costuma ser o tipo do produto (BLUSA, SHORT, SANDALIA).
            head = 0.15 if ref_tokens and tokens[0] in ref_tokens else 0.0
            overlap = len(set(tokens) & ref_tokens) / max(len(set(tokens)), 1)
            score = min(1.0, 0.55 * ratio + 0.30 * overlap + head)
            if best is None or score > best[2]:
                best = (grupo, sub, round(score, 2), original)
        return best


# ---------- Excel preenchido → catálogo ----------

def apply_classifications(catalog, items, editor=None):
    """Grava grupo/subclasse no catálogo; retorna um resumo do que foi feito.

    `items`: [{codigo_barras, descricao, grupo, subclasse, lojas: [{loja, descricao,
    quantidade_catalogo, valor}]}]. Produto que já existe no catálogo (mesmo
    número de código) tem a classificação atualizada; os demais são cadastrados.
    """
    if editor is None:
        from core import catalog_editor as editor
    spelling = {normalize_text(n): n for n in editor.store_names(catalog)}
    # Grupo/subclasse digitados com outra grafia ("Saia", "SAÍA") usam a do catálogo.
    groups, subs = {}, {}
    for product in catalog.get("produtos", []):
        groups.setdefault(normalize_text(product.get("grupo")), product.get("grupo"))
        subs.setdefault((normalize_text(product.get("grupo")), normalize_text(product.get("subclasse"))), product.get("subclasse"))
    summary = {"cadastrados": 0, "atualizados": 0, "erros": []}
    for item in items:
        code = str(item.get("codigo_barras", "")).strip()
        g_key, s_key = normalize_text(item.get("grupo")), normalize_text(item.get("subclasse"))
        item = {**item, "grupo": groups.get(g_key, item.get("grupo")), "subclasse": subs.get((g_key, s_key), item.get("subclasse"))}
        try:
            existing = None
            key = normalize_barcode(code)
            for product in catalog.get("produtos", []):
                if normalize_barcode(product.get("codigo_barras")) == key:
                    existing = product
                    break
            lojas = {}
            for entry in item.get("lojas", []):
                name = spelling.get(normalize_text(entry.get("loja")), entry.get("loja"))
                lojas[normalize_text(name)] = {**entry, "loja": name}
            if existing is not None:
                for entry in existing.get("lojas", []):
                    lojas.setdefault(normalize_text(entry.get("loja")), {
                        "loja": entry.get("loja"), "descricao": entry.get("descricao"),
                        "quantidade_catalogo": entry.get("quantidade_catalogo"), "valor": entry.get("valor"),
                    })
                data = {
                    "codigo_barras": existing["codigo_barras"],
                    "descricao": existing.get("descricao") or item.get("descricao"),
                    "grupo": item["grupo"], "subclasse": item["subclasse"],
                    "situacao": existing.get("situacao") or "ATIVO",
                    "lojas": list(lojas.values()),
                }
                editor.update_product(catalog, existing["codigo_barras"], data)
                summary["atualizados"] += 1
            else:
                data = {
                    "codigo_barras": code, "descricao": item.get("descricao"),
                    "grupo": item["grupo"], "subclasse": item["subclasse"],
                    "situacao": item.get("situacao") or "ATIVO",
                    "lojas": list(lojas.values()),
                }
                editor.add_product(catalog, data)
                summary["cadastrados"] += 1
        except ValueError as error:
            summary["erros"].append(f"{code} – {item.get('descricao', '')}: {error}")
    return summary

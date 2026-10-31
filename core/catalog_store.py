"""Access to the single catalog JSON (catalogo_produtos_estoque_geral.json).

Inside each product -> lojas[] (stores), the file keeps both the catalog data and
the fields that used to live in a separate classification JSON
(the store's `codigo_barras` and `descricao_norm`).
"""
import json
import os
import tempfile
from pathlib import Path


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classification_payload(catalog):
    """Rebuild, in memory, the content of the old estoque_geral_classificacao.json."""
    registros = [
        {
            "loja": l["loja"],
            "codigo_barras": l["codigo_barras"],
            "descricao_norm": l["descricao_norm"],
            "descricao": l["descricao"],
            "grupo": l["grupo"],
            "subclasse": l["subclasse"],
            "situacao": l["situacao"],
        }
        for p in catalog["produtos"]
        for l in p["lojas"]
    ]
    meta = dict(catalog.get("meta", {}).get("classificacao", {}))
    return {"meta": meta, "produtos": registros}


def load_classification_from_catalog(catalog, loader):
    """Call the existing `load_classification(path)` without needing a second file.

    `loader` is core.matcher.load_classification. It still reads a path; here the
    content is generated from the catalog and deleted right afterwards.
    """
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "classificacao.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(classification_payload(catalog), f, ensure_ascii=False)
        return loader(p)

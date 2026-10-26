"""Acesso ao JSON único do catálogo (catalogo_produtos_estoque_geral.json).

O arquivo guarda, dentro de cada produto -> lojas[], tanto os dados do catálogo
quanto os campos que antes ficavam no JSON de classificação
(`codigo_barras` da loja e `descricao_norm`).
"""
import json
import os
import tempfile
from pathlib import Path


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classification_payload(catalog):
    """Reconstrói, em memória, o conteúdo do antigo estoque_geral_classificacao.json."""
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
    """Chama o `load_classification(path)` já existente, sem precisar do 2º arquivo.

    `loader` é a função load_classification de core.matcher. Ela continua lendo um
    caminho; aqui o conteúdo é gerado a partir do catálogo e removido em seguida.
    """
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "classificacao.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(classification_payload(catalog), f, ensure_ascii=False)
        return loader(p)

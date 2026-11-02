"""Lojas da rede. Todos os selects de loja do app usam esta lista.

A ordem de STORES é a ordem de exibição em todo o app (colunas, filtros,
chips e listas): Sitio São João, Palmeiras, Sapiranga, Pedras, Cosméticos.
"""
from utils.normalization import normalize_text

STORES = ("Sitio São João", "Palmeiras", "Sapiranga", "Pedras", "Mix Cosméticos")

_RANK = {normalize_text(store): index for index, store in enumerate(STORES)}


def store_rank(name):
    """Posição da loja na ordem oficial; lojas desconhecidas vão para o fim.

    Aceita a grafia do catálogo/planilha ("pedras", "SITIO SAO JOAO") e
    "Cosméticos" sem o "Mix".
    """
    key = normalize_text(name)
    if key in _RANK:
        return _RANK[key]
    for official, index in _RANK.items():
        if key and (key in official or official in key):
            return index
    return len(STORES)


def store_sort_key(name):
    return (store_rank(name), normalize_text(name))


def order_stores(names):
    """Lojas na ordem oficial (as que não estão em STORES ficam no fim, em ordem alfabética)."""
    return sorted(names, key=store_sort_key)

"""Leitura das planilhas e cruzamento de todas as lojas (sem Qt).

Roda numa thread separada (ui/analysis_worker.py) para a janela não congelar
enquanto as planilhas são lidas. `progress(texto, feito, total)` é chamado a
cada etapa; na thread, ele vira um sinal para a tela.
"""
import pandas as pd

from core.loader import load_sales, load_stock
from core.matcher import build_analysis
from core.models import AnalysisConfig


def _merge_audits(audits):
    audit = {}
    for key in set().union(*(item.keys() for item in audits)) if audits else ():
        if key == "vendas_sem_correspondencia_itens":
            audit[key] = [row for item in audits for row in item.get(key, [])]
        else:
            audit[key] = sum(item.get(key, 0) for item in audits)
    return audit


def run_analysis(info, catalog, classification=None, progress=None):
    """Lê estoque e vendas de cada loja e cruza com o catálogo.

    Devolve (frame, audit). `frame` vem vazio se nenhum produto sobrou depois da
    limpeza; quem chama decide o aviso.
    """
    stores = info["lojas"]
    total = len(stores) * 3  # estoque, vendas e cruzamento de cada loja
    done = 0

    def step(text):
        nonlocal done
        if progress:
            progress(text, done, total)
        done += 1

    frames, audits = [], []
    for position, store_info in enumerate(stores, 1):
        name = store_info["loja"]
        where = f"{name} ({position}/{len(stores)})"
        step(f"Lendo o estoque de {where}")
        stock = load_stock(store_info["estoque_path"])
        step(f"Lendo as vendas de {where}")
        sales = load_sales(store_info["vendas_path"])
        step(f"Cruzando {where} com o catálogo")
        config = AnalysisConfig(
            loja=name,
            data_inicio=info["data_inicio"],
            data_fim=info["data_fim"],
            estoque_path=store_info["estoque_path"],
            vendas_path=store_info["vendas_path"],
        )
        frame, audit = build_analysis(stock, sales, catalog, name, config, classification)
        frames.append(frame)
        audits.append(audit)
        del stock, sales  # libera as planilhas lidas antes de ler a próxima loja

    if progress:
        progress("Montando o dashboard", total, total)
    filled = [item for item in frames if not item.empty]
    frame = pd.concat(filled, ignore_index=True) if filled else pd.DataFrame()
    return frame, _merge_audits(audits)

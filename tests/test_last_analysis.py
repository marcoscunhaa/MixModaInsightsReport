"""Última análise salva: gravação, leitura e textos do card da tela inicial."""
import json
import math
import os
from datetime import date, datetime

import pandas as pd
import pytest

from core.last_analysis import (
    DATA_NAME, META_NAME, LastAnalysisError, LastAnalysisStore, describe_period, describe_saved_at,
)

PERIOD = (date(2026, 10, 1), date(2026, 10, 31))
AUDIT = {"produtos_estoque": 3, "vendas_sem_correspondencia_itens": [{"codigo_barras": "9", "descricao": "X"}]}


def frame():
    return pd.DataFrame({
        "codigo_barras": ["0789", "123", "456"],
        "descricao": ["A", "B", "C"],
        "loja": ["Pedras", "Palmeiras", "Pedras"],
        "quantidade_estoque": [5, 0, -1],
        "quantidade_vendida": [2, 4, 0],
        "valor_vendido": [100.5, 40.0, 0.0],
        "valor_estoque": [50.0, 0.0, -10.0],
        "cobertura": [2.5, 0.0, math.inf],
        "ruptura": [False, True, False],
        "precos_venda": [[{"preco": 50.25, "quantidade": 2}], [], []],
    })


def test_without_saved_analysis(tmp_path):
    store = LastAnalysisStore(tmp_path)
    assert store.meta() is None
    with pytest.raises(LastAnalysisError, match="Nenhuma análise"):
        store.load()


def test_round_trip_keeps_types_and_summary(tmp_path):
    store = LastAnalysisStore(tmp_path)
    original = frame()
    meta = store.save(original, PERIOD, AUDIT, ["Pedras", "Palmeiras", "Pedras"])
    store.wait()
    loaded, period, audit, saved = store.load()
    pd.testing.assert_frame_equal(loaded, original)
    assert loaded.codigo_barras.tolist() == ["0789", "123", "456"]  # zeros à esquerda preservados
    assert math.isinf(loaded.cobertura.iloc[2])
    assert period == PERIOD and audit == AUDIT
    assert saved == meta == store.meta()
    assert meta["lojas"] == ["Palmeiras", "Pedras"]  # sem repetição e na ordem oficial
    assert (meta["produtos"], meta["faturamento"], meta["unidades_vendidas"]) == (3, 140.5, 6)
    assert (meta["data_inicio"], meta["data_fim"]) == ("2026-10-01", "2026-10-31")


def test_new_save_replaces_previous(tmp_path):
    store = LastAnalysisStore(tmp_path)
    store.save(frame(), PERIOD, AUDIT, ["Pedras"])
    second = store.save(frame().head(1), PERIOD, {}, ["Pedras"])
    loaded, _, audit, meta = store.load()  # load espera a gravação em andamento
    assert len(loaded) == 1 and audit == {} and meta["id"] == second["id"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [META_NAME, DATA_NAME]  # sem temporários


def test_summary_without_data_file_is_ignored(tmp_path):
    store = LastAnalysisStore(tmp_path)
    store.save(frame(), PERIOD, AUDIT, ["Pedras"], background=False)
    os.remove(tmp_path / DATA_NAME)
    assert store.meta() is None


def test_corrupted_or_mismatched_files_are_explained(tmp_path):
    store = LastAnalysisStore(tmp_path)
    store.save(frame(), PERIOD, AUDIT, ["Pedras"], background=False)
    (tmp_path / DATA_NAME).write_bytes(b"quebrado")
    with pytest.raises(LastAnalysisError, match="Não foi possível ler"):
        store.load()

    store.save(frame(), PERIOD, AUDIT, ["Pedras"], background=False)
    meta = json.loads((tmp_path / META_NAME).read_text(encoding="utf-8"))
    meta["id"] = "outro"
    (tmp_path / META_NAME).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(LastAnalysisError, match="não conferem"):
        store.load()

    meta["version"] = 999
    (tmp_path / META_NAME).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(LastAnalysisError, match="outra versão"):
        store.load()


def test_period_and_saved_at_texts():
    assert describe_period({"data_inicio": "2026-10-01", "data_fim": "2026-10-31"}) == "01/10 a 31/10/2026"
    assert describe_period({"data_inicio": "2025-12-15", "data_fim": "2026-01-15"}) == "15/12/2025 a 15/01/2026"
    assert describe_period({"data_inicio": "2026-10-05", "data_fim": "2026-10-05"}) == "05/10/2026"
    assert describe_period({}) == "Período não informado"
    now = datetime(2026, 11, 6, 15, 0)
    assert describe_saved_at({"salva_em": "2026-11-06T14:05:00"}, now) == "hoje às 14:05"
    assert describe_saved_at({"salva_em": "2026-11-05T09:12:00"}, now) == "ontem às 09:12"
    assert describe_saved_at({"salva_em": "2026-11-03T18:40:00"}, now) == "03/11/2026 às 18:40"
    assert describe_saved_at({}, now) == "data desconhecida"

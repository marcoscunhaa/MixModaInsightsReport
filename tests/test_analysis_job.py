"""Análise em segundo plano: mesma lógica de antes, com progresso por etapa."""
from datetime import date

import pandas as pd
import pytest

from core import analysis_job, loader


def raw_sheet(column_c, n=6):
    return pd.DataFrame([[f"78900000{i}", f"PRODUTO {i}", column_c, 1.0, 5.0, 9.99, 5.0, 9.99] for i in range(n)])


@pytest.fixture
def sheets(monkeypatch):
    # Estoque tem "UN" na coluna C; vendas, quantidade.
    monkeypatch.setattr(loader, "read_raw", lambda path: raw_sheet("UN" if "estoque" in path else 2.0))


INFO = {"lojas": [{"loja": "Pedras", "estoque_path": "estoque_pedras.xls", "vendas_path": "vendas_pedras.xls"},
                  {"loja": "Palmeiras", "estoque_path": "estoque_palm.xls", "vendas_path": "vendas_palm.xls"}],
        "data_inicio": date(2026, 10, 1), "data_fim": date(2026, 10, 31)}


def test_runs_every_store_and_reports_progress(sheets):
    steps = []
    frame, audit = analysis_job.run_analysis(INFO, {"produtos": []}, None, lambda *step: steps.append(step))
    assert sorted(frame.loja.unique()) == ["Palmeiras", "Pedras"] and len(frame) == 12
    assert audit["produtos_estoque"] == 12
    assert [s[1] for s in steps] == [0, 1, 2, 3, 4, 5, 6] and all(s[2] == 6 for s in steps)
    assert steps[0][0] == "Lendo o estoque de Pedras (1/2)" and steps[-1][0] == "Montando o dashboard"


def test_errors_reach_the_caller(monkeypatch):
    def broken(path):
        raise ValueError("arquivo inválido")
    monkeypatch.setattr(loader, "read_raw", broken)
    with pytest.raises(ValueError):
        analysis_job.run_analysis(INFO, {"produtos": []})

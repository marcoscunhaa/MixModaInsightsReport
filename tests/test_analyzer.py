import pandas as pd

from core.analyzer import filter_analysis


def frame():
    return pd.DataFrame({
        "descricao": ["A", "B", "C", "D"],
        "codigo_barras": ["1", "2", "3", "4"],
        "grupo": ["G1", "G1", "G2", "G2"],
        "subclasse": ["S", "S", "S", "S"],
        "loja": ["Pedras", "Pedras", "Palmeiras", "Pedras"],
        "status_estoque": ["SEM ESTOQUE", "CRÍTICO", "NORMAL", "CRÍTICO"],
        "quantidade_estoque": [0, -3, 5, 1],
    })


def test_status_filters_zero_and_negative():
    df = frame()
    df["status_estoque"] = ["SEM ESTOQUE", "NEGATIVO", "NORMAL", "CRÍTICO"]
    assert list(filter_analysis(df, status="NEGATIVO").descricao) == ["B"]
    assert list(filter_analysis(df, status="SEM ESTOQUE").descricao) == ["A"]


def test_filter_off_keeps_everything():
    assert len(filter_analysis(frame())) == 4

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


def test_only_zero_or_negative_stock():
    assert list(filter_analysis(frame(), somente_zerados=True).descricao) == ["A", "B"]


def test_zero_stock_filter_combines_with_others():
    out = filter_analysis(frame(), loja="Pedras", status="CRÍTICO", somente_zerados=True)
    assert list(out.descricao) == ["B"]


def test_filter_off_keeps_everything():
    assert len(filter_analysis(frame())) == 4

"""Explorar por grupo em cards dentro do dashboard (precisa do PySide6; roda no CI)."""
import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def made(app):
    """Widgets criados no teste são apagados no fim (sem isso o Qt quebra ao fechar o pytest)."""
    widgets = []
    yield widgets.append
    for widget in widgets:
        widget.deleteLater()
    app.processEvents()


def frame():
    return pd.DataFrame({
        "codigo_barras": ["1", "2", "3"],
        "descricao": ["BLUSA P", "BLUSA M", "BATOM"],
        "grupo": ["VESTUARIO FEMININO", "VESTUARIO FEMININO", "MIX COSMÉTICOS"],
        "subclasse": ["BLUSA", "BLUSA", "BATOM"],
        "loja": ["Pedras", "Pedras", "Palmeiras"],
        "quantidade_estoque": [4.0, 2.0, 7.0],
        "quantidade_vendida": [3.0, 1.0, 5.0],
        "valor_estoque": [40.0, 20.0, 35.0],
        "valor_vendido": [90.0, 30.0, 75.0],
        "giro": [42.9, 33.3, 41.7],
    })


def test_browser_navigates_and_goes_back(app, made):
    from ui.dashboard_page import HierarchyBrowser
    paths = []
    browser = HierarchyBrowser(frame(), inline=True, on_path=paths.append)
    made(browser)
    assert browser.list.count() == 2 and browser.back.isHidden()
    browser.open_item(browser.list.item(1))  # grupos em ordem alfabética: VESTUARIO FEMININO
    assert browser.path == [("group", "VESTUARIO FEMININO")] and browser.list.count() == 1
    assert not browser.back.isHidden()
    browser.open_item(browser.list.item(0))
    assert browser.list.count() == 2  # os dois tamanhos da blusa
    browser.go_back(); browser.go_back()
    assert browser.path == [] and browser.list.count() == 2
    assert paths[-1] == []


def test_dashboard_keeps_group_when_filters_change(app, made):
    from ui.dashboard_page import HierarchyBrowser
    browser = HierarchyBrowser(frame(), inline=True)
    made(browser)
    browser.restore([("group", "MIX COSMÉTICOS")])
    assert browser.path == [("group", "MIX COSMÉTICOS")]
    fresh = HierarchyBrowser(frame(), inline=True)
    made(fresh)
    fresh.restore([("group", "NÃO EXISTE")])  # grupo sumiu com o filtro: fica na lista de grupos
    assert fresh.path == [] and fresh.list.count() == 2

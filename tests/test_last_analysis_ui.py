"""Card "Continue de onde parou" da tela inicial (precisa do PySide6; roda no CI)."""
import os
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

CATALOG = Path(__file__).resolve().parent.parent / "data" / "catalogo_produtos_estoque_geral.json"
PERIOD = (date(2026, 10, 1), date(2026, 10, 31))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def frame():
    # Com grupo/subclasse, como toda análise real: abrir a análise salva reaplica o catálogo.
    return pd.DataFrame({"codigo_barras": ["1"], "descricao": ["A"], "loja": ["Pedras"],
                         "grupo": ["SEM CLASSIFICAÇÃO"], "subclasse": ["SEM CLASSIFICAÇÃO"],
                         "quantidade_vendida": [3], "valor_vendido": [90.0], "valor_estoque": [10.0]})


def window(tmp_path):
    from ui.main_window import MainWindow
    catalog = tmp_path / CATALOG.name
    shutil.copy(CATALOG, catalog)
    return MainWindow(catalog, tmp_path)


def test_card_empty_state_does_not_emit(app):
    from ui.widgets import LastAnalysisCard
    card = LastAnalysisCard()
    clicks = []
    card.clicked.connect(lambda: clicks.append(1))
    assert not card.has_analysis() and card.button.isHidden()
    card._activate()
    assert clicks == []
    card.set_meta({"id": "x", "salva_em": "2026-11-06T10:00:00", "data_inicio": "2026-10-01",
                   "data_fim": "2026-10-31", "lojas": ["Pedras", "Palmeiras"], "produtos": 1200,
                   "faturamento": 15432.9, "unidades_vendidas": 380})
    assert card.title.text() == "Análise de 01/10 a 31/10/2026"
    assert card.values["produtos"].text() == "1.200"
    assert card.values["faturamento"].text() == "R$ 15.433"
    card.button.click()
    assert clicks == [1]
    card.set_loading(True)
    card._activate()
    assert clicks == [1]  # enquanto abre, cliques repetidos são ignorados


def test_home_opens_saved_analysis(app, tmp_path, monkeypatch):
    from core.last_analysis import LastAnalysisStore
    assert not window(tmp_path).resume_card.has_analysis()

    saved = LastAnalysisStore(tmp_path).save(frame(), PERIOD, {"a": 1}, ["Pedras"], background=False)
    win = window(tmp_path)
    assert win.resume_card.meta()["id"] == saved["id"]
    shown = []
    monkeypatch.setattr(win, "show_dashboard", lambda *args: shown.append(args))
    win.open_last_analysis()
    app.processEvents()
    assert len(shown) == 1
    loaded, period, audit, analysis_id = shown[0]
    pd.testing.assert_frame_equal(loaded, frame())
    assert (period, audit, analysis_id) == (PERIOD, {"a": 1}, saved["id"])
    assert win.resume_card.button.isEnabled()
    assert QApplication.overrideCursor() is None


def test_same_analysis_reuses_open_dashboard(app, tmp_path, monkeypatch):
    win = window(tmp_path)
    analysis_id = win.save_last_analysis(frame(), PERIOD, {}, [{"loja": "Pedras"}])
    win.last_analysis.wait()
    dashboard = QWidget()
    win.stack.addWidget(dashboard)
    win.dashboard, win.dashboard_id = dashboard, analysis_id
    win.open_home()
    monkeypatch.setattr(win.last_analysis, "load", lambda: pytest.fail("não deveria reler o arquivo"))
    win.open_last_analysis()
    assert win.stack.currentWidget() is dashboard


def test_broken_file_shows_message_and_hides_card(app, tmp_path, monkeypatch):
    from core.last_analysis import DATA_NAME, LastAnalysisStore
    from ui import main_window
    LastAnalysisStore(tmp_path).save(frame(), PERIOD, {}, ["Pedras"], background=False)
    win = window(tmp_path)
    (tmp_path / DATA_NAME).unlink()
    messages = []
    monkeypatch.setattr(main_window, "show_message", lambda *args: messages.append(args))
    win.open_last_analysis()
    app.processEvents()
    assert messages and messages[0][1] == "warning"
    assert not win.resume_card.has_analysis()
    assert QApplication.overrideCursor() is None


def test_generate_runs_in_background_and_opens_the_dashboard(app, tmp_path, monkeypatch):
    import time
    from core import loader
    from ui.dashboard_page import DashboardPage

    def raw(path):
        return pd.DataFrame([[f"78900000{i}", f"PRODUTO {i}", "UN" if "estoque" in path else 2.0, 1.0, 5.0, 9.99, 5.0, 9.99]
                             for i in range(5)])
    monkeypatch.setattr(loader, "read_raw", raw)
    win = window(tmp_path)
    steps = []
    win.analysis.set_progress = lambda text, done, total: steps.append((text, done, total))
    win.generate({"lojas": [{"loja": "Pedras", "estoque_path": "estoque.xls", "vendas_path": "vendas.xls"}],
                  "data_inicio": PERIOD[0], "data_fim": PERIOD[1]})
    assert win._analysis_worker is not None and not win.analysis.generate_button.isEnabled()
    win.generate({"lojas": [], "data_inicio": PERIOD[0], "data_fim": PERIOD[1]})  # segundo clique é ignorado
    deadline = time.time() + 20
    while win._analysis_worker is not None and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert win._analysis_worker is None and win.analysis.generate_button.isEnabled()
    assert isinstance(win.dashboard, DashboardPage) and len(win.dashboard.df) == 5
    assert steps and steps[-1][0] == "Montando o dashboard"
    win.last_analysis.wait()
    win.deleteLater()

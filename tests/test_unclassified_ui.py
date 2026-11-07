"""Lista de produtos sem classificação (precisa do PySide6)."""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from test_unclassified import CATALOG, frame  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_lists_one_row_per_code_and_filters_by_store(app):
    from ui.unclassified_dialog import UnclassifiedDialog
    dialog = UnclassifiedDialog(frame(), CATALOG)
    assert dialog.table.rowCount() == 2  # 4 linhas produto × loja, 2 códigos
    assert dialog.table.item(0, 2).text() == "Palmeiras, Sapiranga, pedras"
    assert "VESTUARIO FEMININO › SAIA" == dialog.table.item(0, 6).text()
    dialog.store.setCurrentText("Palmeiras")
    assert dialog.table.rowCount() == 1
    dialog.store.setCurrentText("Todas as lojas")
    dialog.search.setText("urso")
    assert dialog.table.rowCount() == 1 and dialog.table.item(0, 1).text() == "789002"

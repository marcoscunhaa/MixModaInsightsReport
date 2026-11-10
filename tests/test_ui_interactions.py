"""Copiar código de barras e mover janelas (precisa do PySide6; roda no CI)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QDialog, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def chrome(monkeypatch, tmp_path):
    from ui import window_chrome
    settings = QSettings(str(tmp_path / "posicoes.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(window_chrome, "_settings", lambda: settings)
    return window_chrome


def test_barcode_span_selects_only_the_code():
    from ui.copyable import barcode_span
    text = "SUTIA PROMO  •  7896722660034"
    start, length = barcode_span(text)
    assert text[start:start + length] == "7896722660034"
    assert barcode_span("7896722660034") == (0, 13)
    assert barcode_span("SEM CODIGO") == (0, 10)


def test_double_click_opens_read_only_editor_only_on_barcode_column(app):
    from ui.copyable import is_barcode_column, make_barcode_copyable
    table = QTableWidget(1, 2)
    table.setItem(0, 0, QTableWidgetItem("SUTIA PLUS 50"))
    table.setItem(0, 1, QTableWidgetItem("7896722660010"))
    make_barcode_copyable(table, 1)
    table.show()
    app.processEvents()
    assert is_barcode_column(table, 1) and not is_barcode_column(table, 0)

    assert table.editTriggers() == table.EditTrigger.DoubleClicked
    table.editItem(table.item(0, 0))
    app.processEvents()
    assert table.findChild(QLineEdit) is None          # outras colunas continuam só leitura
    table.setCurrentCell(0, 1)
    table.editItem(table.item(0, 1))
    app.processEvents()
    editor = table.findChild(QLineEdit)
    assert editor is not None and editor.isReadOnly()
    assert editor.selectedText() == "7896722660010"
    assert table.item(0, 1).text() == "7896722660010"  # nada é gravado


def test_ctrl_c_copies_current_cell(app):
    from ui.copyable import make_barcode_copyable
    table = QTableWidget(1, 1)
    table.setItem(0, 0, QTableWidgetItem("7896722660010"))
    make_barcode_copyable(table, 0)
    table.setCurrentCell(0, 0)
    table._copy_shortcut.activated.emit()
    assert QGuiApplication.clipboard().text() == "7896722660010"


def _mouse(widget, kind, global_pos, buttons, modifiers=Qt.KeyboardModifier.NoModifier):
    button = Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton
    local = widget.mapFromGlobal(global_pos)
    event = QMouseEvent(kind, QPointF(local), QPointF(global_pos), button, buttons, modifiers)
    QApplication.sendEvent(widget, event)


def _drag(widget, offset, modifiers=Qt.KeyboardModifier.NoModifier):
    # Posições de tela fixas: o cursor real não anda junto com a janela.
    start = widget.mapToGlobal(QPoint(5, 5))
    left = Qt.MouseButton.LeftButton
    _mouse(widget, QEvent.Type.MouseButtonPress, start, left, modifiers)
    for step in (QPoint(3, 3), offset):
        _mouse(widget, QEvent.Type.MouseMove, start + step, left, modifiers)
    _mouse(widget, QEvent.Type.MouseButtonRelease, start + offset, Qt.MouseButton.NoButton, modifiers)


def _dialog(chrome, title):
    dialog = QDialog()
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    chrome.install_mac_window_chrome(dialog, layout)
    label = QLabel("Arraste aqui")
    layout.addWidget(label)
    table = QTableWidget(2, 2)
    layout.addWidget(table)
    dialog.resize(600, 500)
    dialog.move(200, 200)
    dialog.show()
    QApplication.processEvents()
    return dialog, label, table


def test_drag_on_free_area_moves_window_and_is_remembered(app, chrome):
    dialog, label, _table = _dialog(chrome, "Teste mover")
    before = dialog.pos()
    _drag(label, QPoint(60, 40))
    app.processEvents()
    assert dialog.pos() == before + QPoint(60, 40)
    dialog.close()

    reopened = QDialog()
    reopened.setWindowTitle("Teste mover")
    chrome.install_mac_window_chrome(reopened, QVBoxLayout(reopened))
    assert reopened.pos() == before + QPoint(60, 40)   # reabre onde foi deixado


def test_plain_drag_on_table_does_not_move_but_ctrl_drag_does(app, chrome):
    dialog, _label, table = _dialog(chrome, "Teste tabela")
    before = dialog.pos()
    _drag(table.viewport(), QPoint(50, 30))
    app.processEvents()
    assert dialog.pos() == before
    _drag(table.viewport(), QPoint(50, 30), Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert dialog.pos() == before + QPoint(50, 30)
    dialog.close()


def test_product_picker_marks_several_and_keeps_marks_across_searches(app, chrome):
    import pandas as pd
    from ui.product_picker import ProductPickerDialog
    df = pd.DataFrame({
        "codigo_barras": ["7896722660008", "7896722660005", "7896722660006", "7891000000001"],
        "descricao": ["CONJUNTO RENDA GG", "CONJUNTO RENDA P", "CONJUNTO RENDA M", "CUECA BOXER M"],
        "grupo": ["PECAS INTIMAS"] * 4, "subclasse": ["CONJUNTO", "CONJUNTO", "CONJUNTO", "CUECA"],
        "loja": ["Pedras"] * 4,
    })
    picker = ProductPickerDialog(df, initial_query="conjunto")
    picker.refresh()
    codes = [picker.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(picker.list.count())]
    assert codes == ["7896722660005", "7896722660006", "7896722660008"]   # P, M, GG

    picker._mark_visible()                              # "Marcar todos (3)"
    picker.search.setText("cueca"); picker.refresh()
    picker._toggle_item(picker.list.item(0))            # clique na linha marca
    picker.search.setText("conjunto"); picker.refresh()
    assert all(code in picker.checked for code in codes)
    assert picker.chosen.count() == 4
    assert "4" in picker.apply_button.text()

    picker.toggle("7891000000001")                      # ✕ na coluna de selecionados
    picker._apply()
    assert picker.selected == set(codes)


def test_picker_starts_with_current_selection(app, chrome):
    import pandas as pd
    from ui.product_picker import ProductPickerDialog
    df = pd.DataFrame({"codigo_barras": ["1", "2"], "descricao": ["A", "B"], "grupo": ["G", "G"],
                       "subclasse": ["S", "S"], "loja": ["Pedras", "Pedras"]})
    picker = ProductPickerDialog(df, selected={"2", "999"})
    assert picker.checked == {"2"}                      # código que não existe mais é ignorado
    picker._clear()
    picker._apply()
    assert picker.selected == set()                     # vazio = todos os produtos


def test_selection_filters_the_whole_dashboard(app, chrome):
    import pandas as pd
    from core.loader import SALES_MAP, SALES_REQUIRED, _standardize
    from core.matcher import build_analysis
    from core.models import AnalysisConfig
    from ui.dashboard_page import DashboardPage

    stock = pd.DataFrame([
        ["7896722660005", "CONJUNTO RENDA P", 4, 10.0, 30.0],
        ["7896722660006", "CONJUNTO RENDA M", 6, 10.0, 30.0],
        ["7891000000001", "CUECA BOXER M", 9, 5.0, 15.0],
    ], columns=["codigo_barras", "descricao", "quantidade_estoque", "preco_compra", "preco_venda"])
    sales = _standardize(pd.DataFrame([
        ["7896722660005", "CONJUNTO RENDA P", 2, 10.0, 20.0, 30.0, 60.0, 40.0],
        ["7891000000001", "CUECA BOXER M", 5, 5.0, 25.0, 15.0, 75.0, 50.0],
    ]), SALES_MAP, SALES_REQUIRED)
    frame, audit = build_analysis(stock, sales, {"produtos": []}, "Pedras",
                                  AnalysisConfig("Pedras", None, None, "", ""), None)

    page = DashboardPage(frame, "período", audit)
    assert len(page.current_df()) == 3 and page.selection_bar.isHidden()

    page.set_selection({"7896722660005", "7896722660006"})
    d = page.current_df()
    assert sorted(d.codigo_barras) == ["7896722660005", "7896722660006"]
    assert not page.selection_bar.isHidden() and "2" in page.pick.text()
    assert "CONJUNTO RENDA P" in page.sel_names.text()

    page.set_selection(set())
    assert len(page.current_df()) == 3 and page.selection_bar.isHidden()


def test_inventory_excel_exports_the_whole_stock_ignoring_screen_filters(app, chrome, monkeypatch, tmp_path):
    import pandas as pd
    from openpyxl import load_workbook
    from core.matcher import build_analysis
    from core.models import AnalysisConfig
    from ui import inventory_excel
    from ui.dashboard_page import DashboardPage

    stock = pd.DataFrame([
        ["7896722660005", "CONJUNTO RENDA P", 4, 10.0, 30.0],
        ["7891000000001", "CUECA BOXER M", 9, 5.0, 15.0],
    ], columns=["codigo_barras", "descricao", "quantidade_estoque", "preco_compra", "preco_venda"])
    sales = stock.iloc[0:0].rename(columns={"quantidade_estoque": "quantidade_vendida"})
    frame, audit = build_analysis(stock, sales, {"produtos": []}, "Pedras",
                                  AnalysisConfig("Pedras", None, None, "", ""), None)
    target = tmp_path / "estoque.xlsx"
    monkeypatch.setattr(inventory_excel, "get_save_file", lambda *a, **k: str(target))
    monkeypatch.setattr(inventory_excel.QDesktopServices, "openUrl", lambda *_: True)

    page = DashboardPage(frame, "período", audit)
    assert page.inventory_button.text().endswith("Exportar Estoque")
    page.search.setText("cueca")                       # filtro da tela não reduz o Excel
    assert page.export_inventory() == str(target)
    general = load_workbook(target)["Geral"]
    assert {general.cell(r, 3).value for r in (4, 5)} == {"CONJUNTO RENDA P", "CUECA BOXER M"}

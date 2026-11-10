"""Botões de planilha modelo e importação na página de alertas (precisa do PySide6; roda no CI)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from openpyxl import load_workbook  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from core.stock_alerts import StockAlertStore  # noqa: E402
from exports.alert_template_export import FIRST_ROW  # noqa: E402

CATALOG = {"produtos": [
    {"codigo_barras": "7896719470004", "descricao": "SUNGA ADULTO P", "grupo": "VESTUÁRIO MASCULINO", "subclasse": "SUNGA"},
    {"codigo_barras": "7896719480003", "descricao": "SUNGA ADULTO M", "grupo": "VESTUÁRIO MASCULINO", "subclasse": "SUNGA"},
]}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def chrome(monkeypatch, tmp_path):
    from ui import window_chrome
    settings = QSettings(str(tmp_path / "posicoes.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(window_chrome, "_settings", lambda: settings)
    return window_chrome


def test_download_template_then_import_rules_from_the_alerts_page(app, chrome, monkeypatch, tmp_path):
    from ui import alert_import_dialog
    from ui.stock_alerts import StockAlertRulesDialog

    store = StockAlertStore(tmp_path / "regras.json", tmp_path / "snapshot.json")
    page = StockAlertRulesDialog(CATALOG, store)
    assert page.template_button.text().endswith("Baixar planilha modelo")
    assert page.import_button.text().endswith("Importar planilha")

    target = tmp_path / "modelo.xlsx"
    monkeypatch.setattr(alert_import_dialog, "get_save_file", lambda *a, **k: str(target))
    monkeypatch.setattr(alert_import_dialog.QDesktopServices, "openUrl", lambda *_: True)
    page.download_template()
    wb = load_workbook(target)
    sheet = wb["Alertas"]
    sheet.cell(FIRST_ROW, 1, "7896719480003")
    sheet.cell(FIRST_ROW, 5, 3)
    sheet.cell(FIRST_ROW + 1, 1, "999")  # não existe: fica de fora
    sheet.cell(FIRST_ROW + 1, 5, 1)
    wb.save(target)

    shown = []

    def accept(dialog):
        shown.append((dialog.preview.rules_to_write, dialog.confirm.isEnabled(), dialog.table.rowCount()))
        # Células com widget não têm texto por baixo (o texto se sobrepunha ao cartão).
        assert all(dialog.table.item(r, c).text() == "" for r in range(dialog.table.rowCount()) for c in range(1, 5))
        assert dialog.table.item(0, 0).text().isdigit()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(alert_import_dialog, "get_open_file", lambda *a, **k: str(target))
    monkeypatch.setattr(alert_import_dialog.AlertImportPreviewDialog, "exec", accept)
    assert page.import_rules() == 1
    assert shown == [(1, True, 2)]
    assert [(r["codigo_barras"], r["loja"], r["estoque_minimo"]) for r in store.load_rules()] == [("7896719480003", "*", 3)]
    assert page.hero_count.text() == "1"
    page.deleteLater()

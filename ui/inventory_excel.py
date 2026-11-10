"""Botão "Exportar Estoque": salva o Excel completo (resumo, tabela dinâmica, geral e lojas) e o abre."""
from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from ui.window_chrome import get_save_file, show_message


def default_file_name(today=None):
    return f"Estoque_MixModa_{(today or date.today()).strftime('%d-%m-%Y')}.xlsx"


def export_inventory_excel(parent, df, catalog=None, period_text="", open_after=True):
    """Pergunta onde salvar, gera o arquivo e o abre. Devolve o caminho ou "" se não salvou."""
    from exports.inventory_export import export_inventory_xlsx
    if df is None or df.empty:
        show_message(parent, "information", "Sem estoque", "Esta análise não tem produtos para exportar.")
        return ""
    path = get_save_file(parent, "Salvar Excel do estoque", default_file_name(), "Excel (*.xlsx)", "xlsx")
    if not path:
        return ""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)  # leva alguns segundos com a rede inteira
    try:
        products = export_inventory_xlsx(path, df, catalog, period_text)
    except PermissionError:
        QApplication.restoreOverrideCursor()
        show_message(parent, "critical", "Não foi possível salvar o Excel",
                     "O arquivo está aberto em outro programa. Feche-o ou escolha outro nome e tente de novo.")
        return ""
    except Exception as error:
        QApplication.restoreOverrideCursor()
        show_message(parent, "critical", "Não foi possível gerar o Excel", f"{type(error).__name__}: {error}")
        return ""
    QApplication.restoreOverrideCursor()
    if not (open_after and QDesktopServices.openUrl(QUrl.fromLocalFile(path))):
        show_message(parent, "information", "Excel do estoque gerado",
                     f"{products} produtos exportados.\n\nArquivo salvo em:\n{path}")
    return path

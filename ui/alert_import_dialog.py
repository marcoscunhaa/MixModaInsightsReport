"""Planilha modelo e importação de alertas de estoque (página de regras de alertas).

- `download_alert_template`: salva a planilha modelo (com as regras atuais) e a abre.
- `import_alert_rules`: escolhe a planilha preenchida, mostra a prévia e grava as regras.
"""
from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.alert_import import (
    STATUS_ERROR, STATUS_NEW, STATUS_SAME, STATUS_UPDATE, apply_import, preview_file,
)
from ui.window_chrome import get_open_file, get_save_file, install_mac_window_chrome, show_message

STATUS_LOOK = {
    STATUS_NEW: ("✨  Nova", "statusNew"),
    STATUS_UPDATE: ("↻  Atualiza", "statusUpdate"),
    STATUS_SAME: ("=  Sem mudança", "statusSame"),
    STATUS_ERROR: ("⚠  Problema", "statusError"),
}

PREVIEW_QSS = """
QDialog { background:#F4F7FC; }
QLabel { background:transparent; color:#16233F; }
QFrame#hero { border-radius:22px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #2F5BEA,stop:1 #7C3AED); }
QFrame#hero QLabel { color:#FFFFFF; }
QFrame#hero QLabel#heroIcon { background:rgba(255,255,255,0.18); border-radius:16px; font-size:24px; }
QFrame#hero QLabel#heroEyebrow { color:#DCE3FF; font-size:10px; font-weight:900; letter-spacing:1.5px; }
QFrame#hero QLabel#heroTitle { font-size:22px; font-weight:900; }
QFrame#hero QLabel#heroText { color:#E6EAFF; font-size:12px; }
QFrame#stat { background:#FFFFFF; border:1px solid #DCE6F3; border-radius:16px; }
QFrame#stat QLabel#statNumber { font-size:24px; font-weight:900; }
QFrame#stat QLabel#statCaption { color:#7A879D; font-size:10px; font-weight:900; letter-spacing:1px; }
QFrame#card { background:#FFFFFF; border:1px solid #DCE6F3; border-radius:20px; }
QFrame#card QWidget { background:transparent; }
QTableWidget { background:#FFFFFF; border:none; gridline-color:transparent; outline:none; }
QTableWidget::item { border-bottom:1px solid #EEF2F7; padding:0 6px; color:#233451; }
QTableWidget::item:selected { background:#F5F8FF; color:#16233F; }
QHeaderView::section { background:#FFFFFF; color:#7A879D; border:none; border-bottom:1px solid #E3E9F2;
    padding:8px 6px; font-size:10px; font-weight:900; letter-spacing:1px; }
QLabel#rowName { color:#12213D; font-size:12px; font-weight:800; }
QLabel#rowCode { color:#8A96AA; font-size:10px; }
QLabel#rowNote { color:#7A879D; font-size:10px; }
QLabel#rowNoteError { color:#D9284B; font-size:10px; font-weight:800; }
QLabel#statusNew { background:#E8FAF5; color:#087F6A; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QLabel#statusUpdate { background:#EEF3FF; color:#2F5BEA; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QLabel#statusSame { background:#F1F3F7; color:#7A879D; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QLabel#statusError { background:#FFF0F3; color:#D9284B; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QLabel#limitPill { background:#FFF0F3; color:#D9284B; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QLabel#footNote { color:#7A879D; font-size:11px; }
QPushButton#cancel { background:#FFFFFF; color:#40516E; border:1px solid #D8E2F0; border-radius:12px; padding:10px 22px; font-weight:800; }
QPushButton#cancel:hover { background:#EEF4FF; color:#2854D9; border-color:#AFC2FF; }
QPushButton#confirm { border:none; border-radius:12px; padding:11px 24px; color:#FFFFFF; font-size:12px; font-weight:900;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2F5BEA,stop:1 #7C3AED); }
QPushButton#confirm:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2A51D6,stop:1 #6D2FE0); }
QPushButton#confirm:disabled { background:#DCE3EF; color:#8C99AE; }
"""


def template_file_name(today=None):
    return f"Modelo_Alertas_MixModa_{(today or date.today()).strftime('%d-%m-%Y')}.xlsx"


def download_alert_template(parent, catalog, alert_store, open_after=True):
    """Salva a planilha modelo e a abre. Devolve o caminho, ou "" se não salvou."""
    from exports.alert_template_export import export_alert_template_xlsx
    if not (catalog or {}).get("produtos"):
        show_message(parent, "warning", "Catálogo vazio", "Importe o catálogo antes de gerar a planilha modelo.")
        return ""
    path = get_save_file(parent, "Salvar planilha modelo de alertas", template_file_name(), "Excel (*.xlsx)", "xlsx")
    if not path:
        return ""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        products, prefilled = export_alert_template_xlsx(path, catalog, alert_store.load_rules(), alert_store.load_snapshot())
    except PermissionError:
        QApplication.restoreOverrideCursor()
        show_message(parent, "critical", "Não foi possível salvar",
                     "O arquivo está aberto em outro programa. Feche-o ou escolha outro nome.")
        return ""
    except Exception as error:
        QApplication.restoreOverrideCursor()
        show_message(parent, "critical", "Não foi possível gerar a planilha", f"{type(error).__name__}: {error}")
        return ""
    QApplication.restoreOverrideCursor()
    if not (open_after and QDesktopServices.openUrl(QUrl.fromLocalFile(path))):
        show_message(parent, "information", "Planilha modelo pronta",
                     f"{products} produtos na aba Produtos e {prefilled} regra(s) atual(is) já preenchida(s).\n\n"
                     f"Arquivo salvo em:\n{path}")
    return path


def import_alert_rules(parent, catalog, alert_store, path=None):
    """Escolhe a planilha, mostra a prévia e grava. Devolve quantas regras foram salvas."""
    path = path or get_open_file(parent, "Importar planilha de alertas", "Excel (*.xlsx *.xlsm)")
    if not path:
        return 0
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        preview = preview_file(path, catalog, alert_store.load_rules())
    except ValueError as error:
        QApplication.restoreOverrideCursor()
        show_message(parent, "warning", "Planilha não reconhecida", str(error))
        return 0
    except Exception as error:
        QApplication.restoreOverrideCursor()
        show_message(parent, "critical", "Não foi possível ler a planilha",
                     f"Confira se o arquivo não está aberto em outro programa.\n\n{type(error).__name__}: {error}")
        return 0
    QApplication.restoreOverrideCursor()
    if not preview.lines:
        show_message(parent, "information", "Planilha sem alertas",
                     "Nenhuma linha preenchida na aba Alertas. Cole os códigos, informe o estoque mínimo e tente de novo.")
        return 0
    dialog = AlertImportPreviewDialog(preview, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return 0
    try:
        return apply_import(preview, alert_store)
    except (OSError, ValueError) as error:
        show_message(parent, "critical", "Não foi possível salvar as regras", str(error))
        return 0


class AlertImportPreviewDialog(QDialog):
    """Prévia da importação: o que é novo, o que muda e o que tem problema."""

    def __init__(self, preview, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.setWindowTitle("Importar alertas • Mix Moda")
        self.setStyleSheet(PREVIEW_QSS)
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = min(1000, available.width() - 32) if available else 1000
        height = min(760, available.height() - 48) if available else 760
        self.resize(max(640, width), max(480, height))
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(14)
        install_mac_window_chrome(self, root)
        root.addWidget(self._hero())
        root.addLayout(self._stats())
        root.addWidget(self._table(), 1)
        root.addLayout(self._footer())

    def _hero(self):
        hero = QFrame()
        hero.setObjectName("hero")
        row = QHBoxLayout(hero)
        row.setContentsMargins(24, 18, 24, 18)
        row.setSpacing(16)
        icon = QLabel("📥")
        icon.setObjectName("heroIcon")
        icon.setFixedSize(52, 52)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        for text, name in (("PRÉVIA DA IMPORTAÇÃO", "heroEyebrow"), ("Confira antes de salvar", "heroTitle"),
                           ("Nada foi gravado ainda. As linhas com problema ficam de fora; corrija na planilha e "
                            "importe de novo quando quiser.", "heroText")):
            label = QLabel(text)
            label.setObjectName(name)
            label.setWordWrap(True)
            texts.addWidget(label)
        row.addLayout(texts, 1)
        return hero

    def _stats(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        stats = ((STATUS_NEW, "NOVAS", "#087F6A"), (STATUS_UPDATE, "ATUALIZADAS", "#2F5BEA"),
                 (STATUS_SAME, "SEM MUDANÇA", "#7A879D"), (STATUS_ERROR, "COM PROBLEMA", "#D9284B"))
        for status, caption, color in stats:
            box = QFrame()
            box.setObjectName("stat")
            layout = QVBoxLayout(box)
            layout.setContentsMargins(18, 10, 18, 10)
            layout.setSpacing(0)
            number = QLabel(str(self.preview.count(status)))
            number.setObjectName("statNumber")
            number.setStyleSheet(f"color:{color};")
            layout.addWidget(number)
            label = QLabel(caption)
            label.setObjectName("statCaption")
            layout.addWidget(label)
            row.addWidget(box, 1)
        return row

    def _table(self):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 10)
        # Problemas primeiro: é o que pede atenção.
        order = {STATUS_ERROR: 0, STATUS_UPDATE: 1, STATUS_NEW: 2, STATUS_SAME: 3}
        lines = sorted(self.preview.lines, key=lambda line: (order[line.status], line.linha))
        table = QTableWidget(len(lines), 5)
        table.setHorizontalHeaderLabels(["LINHA", "PRODUTO", "LOJAS", "MÍNIMO", "SITUAÇÃO"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((0, 64), (2, 190), (3, 92), (4, 230)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(column, width)
        for row, line in enumerate(lines):
            texts = (str(line.linha), line.descricao or line.codigo_barras, line.lojas_texto,
                     "" if line.status == STATUS_ERROR else f"≤ {line.estoque_minimo} un.", STATUS_LOOK[line.status][0])
            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if col != 0:
                    item.setForeground(QColor(0, 0, 0, 0))  # o visual vem dos widgets
                table.setItem(row, col, item)
            table.item(row, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            product = QWidget()
            box = QVBoxLayout(product)
            box.setContentsMargins(6, 6, 6, 6)
            box.setSpacing(1)
            name = QLabel(line.descricao or "Produto não identificado")
            name.setObjectName("rowName")
            box.addWidget(name)
            code = QLabel(line.codigo_barras or "sem código")
            code.setObjectName("rowCode")
            code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(code)
            table.setCellWidget(row, 1, product)

            stores = QLabel("" if line.status == STATUS_ERROR else line.lojas_texto)
            stores.setObjectName("rowNote")
            stores.setWordWrap(True)
            table.setCellWidget(row, 2, self._wrap(stores))
            if line.status != STATUS_ERROR:
                table.setCellWidget(row, 3, self._wrap(self._pill(f"≤ {line.estoque_minimo} un.", "limitPill")))

            status = QWidget()
            status_box = QVBoxLayout(status)
            status_box.setContentsMargins(6, 6, 6, 6)
            status_box.setSpacing(3)
            text, style = STATUS_LOOK[line.status]
            pill_row = QHBoxLayout()
            pill_row.addWidget(self._pill(text, style))
            pill_row.addStretch()
            status_box.addLayout(pill_row)
            if line.mensagem:
                note = QLabel(line.mensagem)
                note.setObjectName("rowNoteError" if line.status == STATUS_ERROR else "rowNote")
                note.setWordWrap(True)
                status_box.addWidget(note)
            table.setCellWidget(row, 4, status)
            table.setRowHeight(row, 62 if line.mensagem else 52)
        self.table = table
        layout.addWidget(table)
        return card

    @staticmethod
    def _pill(text, name):
        label = QLabel(text)
        label.setObjectName(name)
        return label

    @staticmethod
    def _wrap(widget):
        holder = QWidget()
        box = QHBoxLayout(holder)
        box.setContentsMargins(6, 0, 6, 0)
        box.addWidget(widget)
        box.addStretch()
        return holder

    def _footer(self):
        row = QHBoxLayout()
        to_save = self.preview.rules_to_write
        lines = len(self.preview.to_apply)
        note = QLabel("🔒  Regras com o mesmo produto e loja são atualizadas, não duplicadas."
                      if to_save else "Nada para importar: tudo já está igual ou precisa de correção na planilha.")
        note.setObjectName("footNote")
        note.setWordWrap(True)
        row.addWidget(note, 1)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(lambda checked=False: self.reject())
        row.addWidget(cancel)
        self.confirm = QPushButton(f"✓  IMPORTAR {to_save} REGRA{'S' if to_save != 1 else ''}")
        if lines and lines != to_save:
            self.confirm.setToolTip(f"{lines} linha(s) da planilha viram {to_save} regra(s): uma por loja marcada.")
        self.confirm.setObjectName("confirm")
        self.confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm.setEnabled(bool(to_save))
        self.confirm.clicked.connect(lambda checked=False: self.accept())
        row.addWidget(self.confirm)
        return row

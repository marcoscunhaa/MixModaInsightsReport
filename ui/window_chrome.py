"""Custom macOS-inspired title bar for application windows."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QApplication, QBoxLayout, QGridLayout, QDialog


class _MacTitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self._target = window
        self.drag_offset = None
        self.setObjectName("MacTitleBar")
        self.setFixedHeight(36)
        self.setStyleSheet(
            "QFrame#MacTitleBar{background:#2B2B2E;border-top-left-radius:9px;"
            "border-top-right-radius:9px;}"
            "QLabel{color:#F5F5F7;font-size:11px;font-weight:800;background:transparent;}"
            "QPushButton{border:0;border-radius:7px;padding:0;}"
            "QPushButton:hover{border:1px solid rgba(0,0,0,0.18);}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(13, 0, 13, 0)
        row.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        self._button(controls, "#FEBC2E", "Minimizar janela", window.showMinimized)
        self._button(controls, "#28C840", "Maximizar ou restaurar janela", self._toggle_maximize)
        self._button(controls, "#FF5F57", "Fechar janela", window.close)
        row.addSpacing(58)
        row.addStretch(1)

        title = QLabel(window.windowTitle())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(title)
        row.addStretch(1)
        row.addLayout(controls)

    @staticmethod
    def _button(layout, color, name, callback):
        button = QPushButton()
        button.setFixedSize(14, 14)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAccessibleName(name)
        button.setToolTip(name)
        button.setStyleSheet(
            f"QPushButton{{background:{color};border:1px solid rgba(0,0,0,0.16);"
            "border-radius:7px;}"
            f"QPushButton:hover{{background:{color};border:1px solid rgba(0,0,0,0.35);}}"
        )
        button.clicked.connect(lambda checked=False: callback())
        layout.addWidget(button)

    def _toggle_maximize(self):
        if self._target.isMaximized():
            self._target.showNormal()
        else:
            self._target.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self._target.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._target.isMaximized():
                self._target.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def install_mac_window_chrome(window, content_layout):
    """Replace native title-bar controls with draggable red/yellow/green controls."""
    if getattr(window, "_mac_title_bar", None):
        return window._mac_title_bar

    screen = window.screen() or QApplication.primaryScreen()
    available = screen.availableGeometry() if screen else None
    if available:
        width = max(480, min(window.width(), available.width() - 24))
        height = max(420, min(window.height(), available.height() - 40))
        window.resize(width, height)
        minimum = window.minimumSize()
        window.setMinimumSize(min(minimum.width(), width), min(minimum.height(), height))

    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    title_bar = _MacTitleBar(window)
    if isinstance(content_layout, QBoxLayout):
        content_layout.insertWidget(0, title_bar)
    elif isinstance(content_layout, QGridLayout):
        positions = []
        for index in range(content_layout.count() - 1, -1, -1):
            position = content_layout.getItemPosition(index)
            item = content_layout.takeAt(index)
            positions.append((position, item))
        positions.reverse()
        columns = max(1, content_layout.columnCount())
        content_layout.addWidget(title_bar, 0, 0, 1, columns)
        for (row, column, row_span, column_span), item in positions:
            content_layout.addItem(item, row + 1, column, row_span, column_span)
    else:
        raise TypeError("A janela precisa usar um layout vertical ou em grade para o título personalizado.")

    window._mac_title_bar = title_bar
    return title_bar

def show_message(parent, level, title, text):
    """Show application messages with the same custom traffic-light window chrome."""
    from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumSize(430, 210)
    dialog.setStyleSheet(
        "QDialog{background:#F4F7FC;}"
        "QLabel#messageText{color:#283954;font-size:12px;}"
        "QPushButton#messageOk{background:#315BEA;color:white;border:0;"
        "border-radius:10px;padding:9px 22px;font-weight:900;}"
        "QPushButton#messageOk:hover{background:#2449CF;}"
    )
    root = QVBoxLayout(dialog)
    root.setContentsMargins(12, 8, 16, 16)
    root.setSpacing(12)
    install_mac_window_chrome(dialog, root)

    colors = {
        "warning": ("!", "#F0A52B"),
        "critical": ("!", "#E84D5B"),
        "information": ("i", "#315BEA"),
    }
    symbol, color = colors.get(level, ("i", "#315BEA"))
    body = QHBoxLayout()
    badge = QLabel(symbol)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(38, 38)
    badge.setStyleSheet(
        f"background:{color};color:white;border-radius:12px;font-size:20px;font-weight:900;"
    )
    body.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    message = QLabel(str(text))
    message.setObjectName("messageText")
    message.setWordWrap(True)
    body.addWidget(message, 1)
    root.addLayout(body, 1)

    actions = QHBoxLayout()
    actions.addStretch(1)
    ok = QPushButton("OK")
    ok.setObjectName("messageOk")
    ok.clicked.connect(lambda checked=False: dialog.accept())
    actions.addWidget(ok)
    root.addLayout(actions)
    dialog.exec()

def get_open_file(parent, title, name_filter):
    from PySide6.QtWidgets import QFileDialog

    dialog = QFileDialog(parent, title)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setNameFilter(name_filter)
    install_mac_window_chrome(dialog, dialog.layout())
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    files = dialog.selectedFiles()
    return files[0] if accepted and files else ""


def get_save_file(parent, title, default_name, name_filter, default_suffix=""):
    from PySide6.QtWidgets import QFileDialog

    dialog = QFileDialog(parent, title)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    dialog.setNameFilter(name_filter)
    if default_suffix:
        dialog.setDefaultSuffix(default_suffix)
    if default_name:
        dialog.selectFile(default_name)
    install_mac_window_chrome(dialog, dialog.layout())
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    files = dialog.selectedFiles()
    return files[0] if accepted and files else ""

def confirm_action(parent, title, message, confirm_label="Excluir"):
    """Show a confirmation dialog with the same app window controls."""
    from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(460)
    dialog.setStyleSheet(
        "QDialog{background:#F4F7FC;}"
        "QLabel#confirmText{color:#283954;font-size:12px;}"
        "QPushButton#cancelAction{background:#FFFFFF;color:#40516E;border:1px solid #D8E2F0;"
        "border-radius:10px;padding:9px 16px;font-weight:800;}"
        "QPushButton#confirmAction{background:#D94152;color:white;border:0;"
        "border-radius:10px;padding:9px 16px;font-weight:900;}"
        "QPushButton#confirmAction:hover{background:#C02E40;}"
    )
    root = QVBoxLayout(dialog)
    root.setContentsMargins(12, 8, 16, 16)
    root.setSpacing(14)
    install_mac_window_chrome(dialog, root)

    label = QLabel(str(message))
    label.setObjectName("confirmText")
    label.setWordWrap(True)
    root.addWidget(label, 1)
    actions = QHBoxLayout()
    actions.addStretch(1)
    cancel = QPushButton("Cancelar")
    cancel.setObjectName("cancelAction")
    cancel.clicked.connect(lambda checked=False: dialog.reject())
    actions.addWidget(cancel)
    confirm = QPushButton(confirm_label)
    confirm.setObjectName("confirmAction")
    confirm.clicked.connect(lambda checked=False: dialog.accept())
    actions.addWidget(confirm)
    root.addLayout(actions)
    return dialog.exec() == QDialog.DialogCode.Accepted

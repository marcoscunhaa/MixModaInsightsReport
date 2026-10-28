"""Custom macOS-inspired title bar for application windows."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QApplication, QSizeGrip


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
        self._button(controls, "#FF5F57", "Fechar janela", window.close)
        self._button(controls, "#FEBC2E", "Minimizar janela", window.showMinimized)
        self._button(controls, "#28C840", "Maximizar ou restaurar janela", self._toggle_maximize)
        row.addLayout(controls)
        row.addStretch(1)

        title = QLabel(window.windowTitle())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(title)
        row.addStretch(1)
        spacer = QFrame()
        spacer.setFixedWidth(58)
        row.addWidget(spacer)

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
    content_layout.insertWidget(0, title_bar)
    window._mac_title_bar = title_bar
    grip = QSizeGrip(window)
    content_layout.addWidget(grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
    window._mac_size_grip = grip
    return title_bar

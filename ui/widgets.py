from utils.formatting import brl, br_number
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect

class ShadowMixin:
    def add_shadow(self, blur=28, y=7, opacity=35):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur); shadow.setOffset(0, y)
        from PySide6.QtGui import QColor
        shadow.setColor(QColor(24, 39, 75, opacity))
        self.setGraphicsEffect(shadow)

class Card(QFrame):
    clicked = Signal()
    def __init__(self, title, value="", accent="#2854D9", icon="", parent=None):
        super().__init__(parent); self.setObjectName("KpiCard"); self.setCursor(Qt.PointingHandCursor)
        l=QVBoxLayout(self); l.setContentsMargins(17,14,17,15); l.setSpacing(7)
        top=QHBoxLayout(); a=QLabel(title); a.setStyleSheet(f"color:{accent};font-size:11px;font-weight:900;") ; top.addWidget(a); top.addStretch()
        if icon:
            ic=QLabel(icon); ic.setStyleSheet(f"color:{accent};font-size:18px;font-weight:900;"); top.addWidget(ic)
        l.addLayout(top)
        b=QLabel(value); b.setStyleSheet("color:#12213D;font-size:22px;font-weight:900;"); l.addWidget(b)
        line=QFrame(); line.setFixedHeight(5); line.setStyleSheet(f"background:{accent};border-radius:2px;"); l.addWidget(line)
        self.add_shadow()
    def add_shadow(self):
        from PySide6.QtGui import QColor
        shadow=QGraphicsDropShadowEffect(self); shadow.setBlurRadius(25); shadow.setOffset(0,6); shadow.setColor(QColor(25,43,78,28)); self.setGraphicsEffect(shadow)
    def mousePressEvent(self,e): self.clicked.emit(); super().mousePressEvent(e)

class RankCard(QFrame):
    clicked=Signal()
    def __init__(self,position,product,qty,accent,revenue=0,parent=None):
        super().__init__(parent); self.setObjectName("TopRank"); self.setCursor(Qt.PointingHandCursor)
        l=QHBoxLayout(self); l.setContentsMargins(14,12,14,12); l.setSpacing(12)
        p=QLabel(position); p.setFixedWidth(42); p.setAlignment(Qt.AlignCenter); p.setStyleSheet(f"font-size:22px;font-weight:900;color:{accent};background:#F4F7FC;border-radius:12px;padding:5px;"); l.addWidget(p)
        box=QVBoxLayout(); name=QLabel(str(product)); name.setStyleSheet("font-weight:900;color:#182641;font-size:12px;"); name.setWordWrap(True); box.addWidget(name)
        q=QLabel(f"{br_number(qty,0)} unidades  •  {brl(revenue)} faturamento"); q.setStyleSheet(f"color:{accent};font-size:11px;font-weight:800;"); box.addWidget(q); l.addLayout(box,1); self.add_shadow()
    def add_shadow(self):
        from PySide6.QtGui import QColor
        shadow=QGraphicsDropShadowEffect(self); shadow.setBlurRadius(20); shadow.setOffset(0,5); shadow.setColor(QColor(25,43,78,22)); self.setGraphicsEffect(shadow)
    def mousePressEvent(self,e): self.clicked.emit(); super().mousePressEvent(e)


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


class FeatureCard(QFrame):
    """Card de funcionalidade da tela inicial: emoji, título, descrição e chamada.

    O card inteiro é clicável (mouse, Enter ou espaço). `primary` destaca a ação
    principal com fundo em degradê.
    """
    clicked = Signal()

    def __init__(self, emoji, title, text, cta, accent, primary=False, parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(232)
        if primary:
            background = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #2F5BEA,stop:1 #7C3AED)"
            hover = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #2A51D6,stop:1 #6D2FE0)"
            title_color, text_color, cta_color = "#FFFFFF", "#E6EAFF", "#FFFFFF"
            icon_bg, border, hover_border = "rgba(255,255,255,0.18)", "transparent", "transparent"
        else:
            background, hover = "#FFFFFF", "#FBFCFF"
            title_color, text_color, cta_color = "#12213D", "#66758F", accent
            icon_bg, border, hover_border = _rgba(accent, 0.12), "#DCE6F3", accent
        self.setStyleSheet(
            f"QFrame#FeatureCard{{background:{background};border:1px solid {border};border-radius:22px;}}"
            f"QFrame#FeatureCard:hover, QFrame#FeatureCard:focus{{background:{hover};border:1px solid {hover_border};}}"
            "QFrame#FeatureCard QLabel{background:transparent;border:none;}"
            f"QLabel#FeatureIcon{{background:{icon_bg};border-radius:16px;font-size:26px;}}"
            f"QLabel#FeatureTitle{{color:{title_color};font-size:18px;font-weight:900;}}"
            f"QLabel#FeatureText{{color:{text_color};font-size:12px;}}"
            f"QLabel#FeatureCta{{color:{cta_color};font-size:12px;font-weight:900;letter-spacing:0.5px;}}"
            f"QLabel#FeatureTag{{color:{cta_color};background:{icon_bg};border-radius:9px;"
            "padding:3px 9px;font-size:10px;font-weight:900;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        top = QHBoxLayout()
        icon = QLabel(emoji)
        icon.setObjectName("FeatureIcon")
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(icon)
        top.addStretch()
        self.tag = QLabel("")
        self.tag.setObjectName("FeatureTag")
        self.tag.hide()
        top.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        layout.addSpacing(4)
        name = QLabel(title)
        name.setObjectName("FeatureTitle")
        layout.addWidget(name)
        body = QLabel(text)
        body.setObjectName("FeatureText")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)
        action = QLabel(f"{cta}  →")
        action.setObjectName("FeatureCta")
        layout.addWidget(action)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        from PySide6.QtGui import QColor
        shadow.setColor(QColor(47, 91, 234, 70) if primary else QColor(25, 43, 78, 26))
        self.setGraphicsEffect(shadow)

    def set_tag(self, text):
        self.tag.setText(text)
        self.tag.setVisible(bool(text))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


TONE_COLORS = {"good": "#087F6A", "warn": "#B77900", "bad": "#D9284B"}


class KpiCard(QFrame):
    """Card de KPI: emoji, nome claro, valor e uma frase que explica o número.

    `tone` colore o valor/frase: good (verde), warn (âmbar), bad (vermelho).
    """
    clicked = Signal()

    def __init__(self, label, value, hint, accent, emoji, tone="neutral", clickable=False, parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard2")
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Clique para ver a lista de produtos")
        value_color = TONE_COLORS["bad"] if tone == "bad" else "#12213D"
        hint_color = TONE_COLORS.get(tone, "#7A879D")
        self.setStyleSheet(
            "QFrame#KpiCard2{background:#FFFFFF;border:1px solid #DCE6F3;border-radius:18px;}"
            f"QFrame#KpiCard2:hover{{border:1px solid {accent if clickable else '#DCE6F3'};"
            f"background:{'#FBFCFF' if clickable else '#FFFFFF'};}}"
            "QFrame#KpiCard2 QLabel{background:transparent;border:none;}"
            f"QLabel#kpiIcon{{background:{_rgba(accent, 0.12)};border-radius:10px;font-size:16px;}}"
            "QLabel#kpiLabel{color:#40516E;font-size:12px;font-weight:800;}"
            f"QLabel#kpiMore{{color:{accent};font-size:10px;font-weight:900;}}"
            f"QLabel#kpiValue{{color:{value_color};font-size:23px;font-weight:900;}}"
            f"QLabel#kpiHint{{color:{hint_color};font-size:11px;font-weight:{'800' if tone != 'neutral' else '600'};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(9)
        icon = QLabel(emoji)
        icon.setObjectName("kpiIcon")
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(icon)
        name = QLabel(label)
        name.setObjectName("kpiLabel")
        top.addWidget(name, 1)
        if clickable:
            more = QLabel("Ver lista ›")
            more.setObjectName("kpiMore")
            top.addWidget(more)
        layout.addLayout(top)
        self.value = QLabel(str(value))
        self.value.setObjectName("kpiValue")
        layout.addWidget(self.value)
        self.hint = QLabel(str(hint))
        self.hint.setObjectName("kpiHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch(1)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        from PySide6.QtGui import QColor
        shadow.setColor(QColor(25, 43, 78, 20))
        self.setGraphicsEffect(shadow)

    def mouseReleaseEvent(self, event):
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class StatusFilterBar(QFrame):
    """Pílulas de status com contagem; uma selecionada por vez.

    Mantém a interface do combo antigo (currentText/setCurrentText e o sinal
    currentTextChanged) para o dashboard não precisar mudar em outros pontos.
    """
    currentTextChanged = Signal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setStyleSheet("QFrame#StatusBar{background:transparent;border:none;} QFrame#StatusBar QLabel{background:transparent;}")
        from PySide6.QtWidgets import QButtonGroup, QPushButton
        self._options = options
        self._buttons = {}
        self._current = options[0][0]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        title = QLabel("STATUS DO ESTOQUE")
        title.setStyleSheet("color:#7A879D;font-size:10px;font-weight:900;letter-spacing:1px;padding-right:4px;")
        layout.addWidget(title)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for value, label, emoji, color, tip in options:
            button = QPushButton()
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"{label}: {tip}")
            button.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#40516E;border:1px solid #DCE6F3;border-radius:15px;"
                "padding:6px 12px;font-size:11px;font-weight:800;}"
                f"QPushButton:hover{{border-color:{color};color:{color};}}"
                f"QPushButton:checked{{background:{color};border-color:{color};color:#FFFFFF;}}"
                "QPushButton:disabled{background:#F7F8FB;color:#B4BECD;border-color:#EEF1F6;}"
            )
            button.clicked.connect(lambda checked=False, v=value: self.setCurrentText(v))
            group.addButton(button)
            layout.addWidget(button)
            self._buttons[value] = (button, label, emoji)
        layout.addStretch()
        self._buttons[self._current][0].setChecked(True)
        self.set_counts({})

    def currentText(self):
        return self._current

    def setCurrentText(self, value):
        if value not in self._buttons:
            return
        self._buttons[value][0].setChecked(True)
        if value != self._current:
            self._current = value
            self.currentTextChanged.emit(value)

    def set_counts(self, counts):
        """Atualiza o número em cada pílula; status sem produtos ficam desativados."""
        for value, (button, label, emoji) in self._buttons.items():
            count = counts.get(value, 0)
            button.setText(f"{emoji}  {label}  {br_number(count, 0)}")
            button.setEnabled(bool(count) or value == self._current or value == self._options[0][0])

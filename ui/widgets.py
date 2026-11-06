from utils.formatting import brl, br_number
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QWidget

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


class LastAnalysisCard(QFrame):
    """Faixa "Continue de onde parou" da tela inicial.

    Com análise salva: painel escuro com período, quando foi gerada, lojas,
    três números-resumo e o botão ABRIR ANÁLISE (o card inteiro é clicável).
    Sem análise: estado vazio discreto explicando que a próxima aparece aqui.
    Só lê o resumo pequeno (dict); nenhum dado pesado passa por aqui.
    """
    clicked = Signal()

    _STYLE = (
        "QFrame#ResumeCard{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        "stop:0 #0E1B3D,stop:0.55 #172C66,stop:1 #2B2470);border:1px solid #22356F;border-radius:22px;}"
        "QFrame#ResumeCard:hover, QFrame#ResumeCard:focus{border:1px solid #7F96FF;}"
        "QFrame#ResumeCard[empty=\"true\"], QFrame#ResumeCard[empty=\"true\"]:hover{background:#FFFFFF;border:1px dashed #C9D5EA;}"
        "QFrame#ResumeCard QLabel{background:transparent;border:none;}"
        "QFrame#ResumeCard QWidget#ResumeStats{background:transparent;}"
        "QFrame#ResumeCard QLabel#ResumeIcon{background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.16);"
        "border-radius:16px;font-size:24px;}"
        "QFrame#ResumeCard[empty=\"true\"] QLabel#ResumeIcon{background:#EEF3FF;border:none;}"
        "QFrame#ResumeCard QLabel#ResumeEyebrow{color:#9DB0FF;font-size:10px;font-weight:900;letter-spacing:1.6px;}"
        "QFrame#ResumeCard QLabel#ResumeWhen{color:#D9E1FF;background:rgba(255,255,255,0.10);border-radius:9px;"
        "padding:3px 9px;font-size:10px;font-weight:800;}"
        "QFrame#ResumeCard QLabel#ResumeTitle{color:#FFFFFF;font-size:19px;font-weight:900;}"
        "QFrame#ResumeCard[empty=\"true\"] QLabel#ResumeTitle{color:#12213D;font-size:15px;}"
        "QFrame#ResumeCard QLabel#ResumeText{color:#66758F;font-size:12px;}"
        "QFrame#ResumeCard QLabel#ResumeStore{color:#E6EBFF;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.14);"
        "border-radius:10px;padding:3px 10px;font-size:11px;font-weight:700;}"
        "QFrame#ResumeCard QLabel#ResumeValue{color:#FFFFFF;font-size:17px;font-weight:900;}"
        "QFrame#ResumeCard QLabel#ResumeLabel{color:#9DB0FF;font-size:10px;font-weight:800;letter-spacing:0.8px;}"
        "QFrame#ResumeDivider{background:rgba(255,255,255,0.14);border:none;}"
        "QPushButton#ResumeOpen{background:#FFFFFF;color:#172C66;border-radius:14px;padding:13px 22px;"
        "font-size:12px;font-weight:900;letter-spacing:0.6px;}"
        "QPushButton#ResumeOpen:hover{background:#E9EEFF;}"
        "QPushButton#ResumeOpen:pressed{background:#D7E0FF;}"
        "QPushButton#ResumeOpen:disabled{background:rgba(255,255,255,0.55);color:#172C66;}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QPushButton
        self.setObjectName("ResumeCard")
        self.setStyleSheet(self._STYLE)
        self.setMinimumHeight(118)
        self._meta = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(18)
        self.icon = QLabel("🕘")
        self.icon.setObjectName("ResumeIcon")
        self.icon.setFixedSize(56, 56)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(10)
        self.eyebrow = QLabel("CONTINUE DE ONDE PAROU")
        self.eyebrow.setObjectName("ResumeEyebrow")
        head.addWidget(self.eyebrow)
        self.when = QLabel()
        self.when.setObjectName("ResumeWhen")
        head.addWidget(self.when)
        head.addStretch()
        info.addLayout(head)
        self.title = QLabel()
        self.title.setObjectName("ResumeTitle")
        info.addWidget(self.title)
        self.text = QLabel()
        self.text.setObjectName("ResumeText")
        self.text.setWordWrap(True)
        info.addWidget(self.text)
        self.stores = QHBoxLayout()
        self.stores.setSpacing(6)
        info.addLayout(self.stores)
        layout.addLayout(info, 1)

        self.stats = QWidget(self)
        self.stats.setObjectName("ResumeStats")
        stats = QHBoxLayout(self.stats)
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setSpacing(18)
        self.values = {}
        for index, (key, label) in enumerate(
            (("produtos", "PRODUTOS"), ("faturamento", "FATURAMENTO"), ("unidades_vendidas", "VENDIDAS"))
        ):
            if index:
                divider = QFrame()
                divider.setObjectName("ResumeDivider")
                divider.setFixedSize(1, 36)
                stats.addWidget(divider)
            box = QVBoxLayout()
            box.setSpacing(2)
            value = QLabel()
            value.setObjectName("ResumeValue")
            box.addWidget(value)
            caption = QLabel(label)
            caption.setObjectName("ResumeLabel")
            box.addWidget(caption)
            stats.addLayout(box)
            self.values[key] = value
        layout.addWidget(self.stats, 0, Qt.AlignmentFlag.AlignVCenter)

        self.button = QPushButton("ABRIR ANÁLISE  →")
        self.button.setObjectName("ResumeOpen")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._activate)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(34)
        self.shadow.setOffset(0, 10)
        self.setGraphicsEffect(self.shadow)
        self.set_meta(None)

    def has_analysis(self):
        return self._meta is not None

    def meta(self):
        return self._meta

    def set_meta(self, meta):
        from PySide6.QtGui import QColor
        from core.last_analysis import describe_period, describe_saved_at
        self._meta = meta
        empty = meta is None
        self.setProperty("empty", empty)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setCursor(Qt.CursorShape.ArrowCursor if empty else Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus if empty else Qt.FocusPolicy.StrongFocus)
        self.shadow.setColor(QColor(25, 43, 78, 14) if empty else QColor(23, 44, 102, 80))
        while self.stores.count():
            item = self.stores.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.when.setVisible(not empty)
        self.stats.setVisible(not empty)
        self.button.setVisible(not empty)
        self.text.setVisible(empty)
        self.eyebrow.setVisible(not empty)
        if empty:
            self.icon.setText("🗂️")
            self.title.setText("Nenhuma análise salva ainda")
            self.text.setText(
                "Ao gerar uma análise, ela fica guardada aqui para reabrir o dashboard num clique, "
                "sem selecionar as planilhas de novo."
            )
            self.setToolTip("")
            return
        self.icon.setText("🕘")
        self.when.setText(f"Gerada {describe_saved_at(meta)}")
        period = describe_period(meta)
        self.title.setText(f"Análise de {period}")
        for store in meta.get("lojas", []):
            chip = QLabel(f"🏬 {store}")
            chip.setObjectName("ResumeStore")
            self.stores.addWidget(chip)
        self.stores.addStretch()
        self.values["produtos"].setText(br_number(meta.get("produtos", 0), 0))
        self.values["faturamento"].setText(brl(meta.get("faturamento", 0), 0))
        self.values["unidades_vendidas"].setText(br_number(meta.get("unidades_vendidas", 0), 0))
        self.setToolTip("Reabre o dashboard desta análise sem reprocessar as planilhas")
        self.set_loading(False)

    def set_loading(self, loading):
        self.button.setEnabled(not loading)
        self.button.setText("ABRINDO…" if loading else "ABRIR ANÁLISE  →")

    def _activate(self):
        if self._meta is not None and self.button.isEnabled():
            self.clicked.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self._activate()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._activate()
            return
        super().keyPressEvent(event)

"""Peças visuais repetidas entre as telas, para todas seguirem o mesmo desenho.

- Cabeçalho de página: voltar sempre no canto esquerdo, título e "onde estou" logo ao lado,
  ações da tela à direita (a principal por último).
- Passo numerado (1, 2, 3) para telas em que o usuário segue uma ordem.
- Título de seção com uma frase curta dizendo o que dá para fazer ali.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def button(text, kind="", tooltip="", on_click=None):
    """Botão com a hierarquia do app: "", Primary, Secondary, Success, Ghost, Link, Danger."""
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click is not None:
        b.clicked.connect(lambda checked=False: on_click())
    return b


class PageHeader(QHBoxLayout):
    """Linha de topo: [← voltar]  Título / caminho  ............  [ações]."""

    def __init__(self, title, crumb="", back_text="← Início", on_back=None):
        super().__init__()
        self.setSpacing(14)
        self.back = None
        if on_back is not None:
            self.back = button(back_text, "Ghost", "Voltar para a tela anterior", on_back)
            self.addWidget(self.back, 0, Qt.AlignmentFlag.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("PageTitle")
        texts.addWidget(self.title)
        self.crumb = QLabel(crumb)
        self.crumb.setObjectName("Crumb")
        self.crumb.setVisible(bool(crumb))
        texts.addWidget(self.crumb)
        self.addLayout(texts)
        self.addStretch(1)

    def set_crumb(self, text):
        self.crumb.setText(text)
        self.crumb.setVisible(bool(text))

    def add_action(self, widget):
        self.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget


def step_header(number, title, hint=""):
    """Cabeçalho de passo: bolinha numerada, título e uma dica curta abaixo."""
    box = QVBoxLayout()
    box.setSpacing(4)
    row = QHBoxLayout()
    row.setSpacing(10)
    badge = QLabel(str(number))
    badge.setObjectName("StepBadge")
    badge.setFixedSize(26, 26)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(badge)
    label = QLabel(title)
    label.setObjectName("StepTitle")
    row.addWidget(label)
    row.addStretch(1)
    box.addLayout(row)
    if hint:
        text = QLabel(hint)
        text.setObjectName("SectionHint")
        text.setWordWrap(True)
        text.setContentsMargins(36, 0, 0, 0)
        box.addWidget(text)
    return box


def section_header(title, hint=""):
    """Título de seção do dashboard com a dica de uso logo abaixo."""
    frame = QFrame()
    frame.setObjectName("PanelBody")
    box = QVBoxLayout(frame)
    box.setContentsMargins(2, 10, 2, 0)
    box.setSpacing(2)
    label = QLabel(title)
    label.setObjectName("SectionTitle")
    box.addWidget(label)
    if hint:
        text = QLabel(hint)
        text.setObjectName("SectionHint")
        text.setWordWrap(True)
        box.addWidget(text)
    return frame


def divider():
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line

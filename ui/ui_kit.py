"""Peças visuais repetidas entre as telas, para todas seguirem o mesmo desenho.

- Cabeçalho de página: voltar sempre no canto esquerdo, título e "onde estou" logo ao lado,
  ações da tela à direita (a principal por último).
- Passo numerado (1, 2, 3) para telas em que o usuário segue uma ordem.
- Título de seção com uma frase curta dizendo o que dá para fazer ali.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

# Cores da marca Mix Moda (fachada amarela com letreiro vermelho), em tons um pouco
# mais profundos para ficarem elegantes sobre o fundo claro do app. O amarelo puro
# não tem contraste para texto em fundo branco: ele entra em faixas, degradês e
# detalhes; os textos da marca usam o vermelho (ou o dourado escuro).
BRAND_RED = "#D3203B"
BRAND_RED_DARK = "#A8162E"
BRAND_YELLOW = "#FFC20E"
BRAND_GOLD = "#B57E00"
BRAND_GRADIENT = f"qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {BRAND_YELLOW},stop:1 {BRAND_RED})"
BRAND_GRADIENT_DIAGONAL = f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FFB81C,stop:1 {BRAND_RED})"


def brand_html(suffix="", suffix_color="#102A56"):
    """'MIX MODA' em vermelho da marca, seguido de um complemento (ex.: INSIGHTS) em azul-marinho."""
    extra = f"&nbsp;<span style='color:{suffix_color};'>{suffix}</span>" if suffix else ""
    return f"<span style='color:{BRAND_RED};'>MIX MODA</span>{extra}"


def brand_eyebrow(text):
    """Linha pequena acima dos títulos: 'MIX MODA' em vermelho, ponto dourado e o complemento."""
    label = QLabel(
        f"<span style='color:{BRAND_RED};'>MIX MODA</span>"
        f"<span style='color:{BRAND_YELLOW};'>&nbsp;&nbsp;●&nbsp;&nbsp;</span>"
        f"<span style='color:#7A879D;'>{text}</span>"
    )
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setStyleSheet("font-size:11px;font-weight:900;letter-spacing:1.5px;background:transparent;")
    return label


def brand_bar(width=96, height=4):
    """Faixa curta amarelo → vermelho, assinatura visual da marca sob os títulos."""
    bar = QFrame()
    bar.setFixedSize(width, height)
    bar.setStyleSheet(f"background:{BRAND_GRADIENT};border:none;border-radius:{height // 2}px;")
    return bar


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

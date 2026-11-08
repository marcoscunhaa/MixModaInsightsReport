"""Card do explorador (grupo › subclasse › produto) e cor estável por nome.

Fica fora do dashboard para o Explorar estoque não carregar pandas,
gráficos e PDF só para desenhar os cards.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

SUBCLASS_COLORS = ["#5B6CFF","#E85D8A","#00A88F","#FFB52E","#19A9C7","#8B6FE8","#FF7A59","#D94D9A","#36A269","#F06A9B","#4B8EF7","#12B8A6"]


def _stable_color(text):
    return SUBCLASS_COLORS[sum(ord(c) for c in str(text)) % len(SUBCLASS_COLORS)]


class ExplorerCard(QFrame):
    """Card clicável da grade (grupo, subclasse ou produto).

    O card desenha a própria borda arredondada, a faixa colorida à esquerda e o
    hover; a lista que o contém (objectName "CardGrid") não desenha nada por trás.
    `flat` foi mantido por compatibilidade: o visual é o mesmo nos dois casos.
    """

    def __init__(self, emoji, title, subtitle, value, accent, parent=None, flat=True, copyable_subtitle=False):
        super().__init__(parent); self.setObjectName("ExplorerCard")
        self.setToolTip("Clique para abrir")
        self.setStyleSheet(
            f"QFrame#ExplorerCard{{background:#FFFFFF;border:1px solid #DCE6F3;border-left:5px solid {accent};border-radius:14px;}}"
            f"QFrame#ExplorerCard:hover{{background:#F7FAFF;border:1px solid {accent};border-left:5px solid {accent};}}"
            "QFrame#ExplorerCard QLabel{background:transparent;border:none;}"
        )
        l=QHBoxLayout(self); l.setContentsMargins(16,12,12,12); l.setSpacing(12)
        text=QVBoxLayout(); text.setSpacing(3)
        name=QLabel(str(title)); name.setStyleSheet("font-size:13px;font-weight:900;color:#142B52;"); name.setWordWrap(True); text.addWidget(name)
        sub=QLabel(str(subtitle)); sub.setStyleSheet("font-size:11px;font-weight:700;color:#73829A;"); text.addWidget(sub)
        if copyable_subtitle:
            # Subtítulo do card de produto traz o código de barras: dois cliques selecionam, Ctrl+C copia.
            from ui.copyable import make_label_copyable
            make_label_copyable(sub)
        val=QLabel(str(value)); val.setStyleSheet(f"font-size:11px;font-weight:900;color:{accent};"); val.setWordWrap(True); text.addWidget(val); l.addLayout(text,1)
        arrow=QLabel("›"); arrow.setStyleSheet(f"font-size:26px;font-weight:300;color:{accent};"); l.addWidget(arrow)

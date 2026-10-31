"""Explorer card (group › subclass › product) and a stable color per name.

Kept outside the dashboard so Explore stock does not load pandas, charts
and PDF just to draw the cards.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

SUBCLASS_COLORS = ["#5B6CFF","#E85D8A","#00A88F","#FFB52E","#19A9C7","#8B6FE8","#FF7A59","#D94D9A","#36A269","#F06A9B","#4B8EF7","#12B8A6"]


def _stable_color(text):
    return SUBCLASS_COLORS[sum(ord(c) for c in str(text)) % len(SUBCLASS_COLORS)]


class ExplorerCard(QFrame):
    def __init__(self, emoji, title, subtitle, value, accent, parent=None, flat=True):
        super().__init__(parent); self.setObjectName("ExplorerCard")
        border="none" if flat else "1px solid #DCE6F3"; radius="0px" if flat else "18px"
        self.setStyleSheet(f"QFrame#ExplorerCard{{background:#FFFFFF;border:{border};border-left:6px solid {accent};border-radius:{radius};}} QFrame#ExplorerCard:hover{{background:#F7FAFF;}}")
        l=QHBoxLayout(self); l.setContentsMargins(13,14,14,14); l.setSpacing(12)
        text=QVBoxLayout(); text.setSpacing(3)
        name=QLabel(str(title)); name.setStyleSheet("font-size:13px;font-weight:900;color:#142B52;"); name.setWordWrap(True); text.addWidget(name)
        sub=QLabel(str(subtitle)); sub.setStyleSheet("font-size:10px;font-weight:700;color:#73829A;"); text.addWidget(sub)
        val=QLabel(str(value)); val.setStyleSheet(f"font-size:10px;font-weight:900;color:{accent};"); text.addWidget(val); l.addLayout(text,1)
        arrow=QLabel("›"); arrow.setStyleSheet(f"font-size:25px;font-weight:300;color:{accent};"); l.addWidget(arrow)

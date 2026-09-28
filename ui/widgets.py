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

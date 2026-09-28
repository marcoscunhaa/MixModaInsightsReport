from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QLabel,QHBoxLayout
class CatalogPage(QWidget):
    product_clicked=Signal(object)
    def __init__(self,catalog,parent=None):
        super().__init__(parent); self.catalog=catalog; l=QVBoxLayout(self)
        t=QLabel("CATÁLOGO DE PRODUTOS"); t.setObjectName("Title"); l.addWidget(t); l.addWidget(QLabel("Exploração por grupo → subclasse → produto"))
        top=QHBoxLayout(); self.group=QComboBox(); self.group.addItem("Todos"); self.group.addItems(sorted({p.get("grupo","") for p in catalog.get("produtos",[]) if p.get("grupo")}))
        self.sub=QComboBox(); self.sub.addItem("Todas"); self.search=QLineEdit(); self.search.setPlaceholderText("Buscar produto, código ou descrição...")
        top.addWidget(self.group); top.addWidget(self.sub); top.addWidget(self.search); l.addLayout(top)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Código","Produto","Grupo","Subclasse"]); self.table.cellDoubleClicked.connect(self.open_row); l.addWidget(self.table)
        self.group.currentTextChanged.connect(self.refresh_subclasses); self.sub.currentTextChanged.connect(self.refresh); self.search.textChanged.connect(self.refresh); self.refresh()
    def refresh_subclasses(self):
        self.sub.blockSignals(True); self.sub.clear(); self.sub.addItem("Todas"); g=self.group.currentText()
        self.sub.addItems(sorted({p.get("subclasse","") for p in self.catalog.get("produtos",[]) if g=="Todos" or p.get("grupo")==g})); self.sub.blockSignals(False); self.refresh()
    def refresh(self):
        g=self.group.currentText(); s=self.sub.currentText(); q=self.search.text().upper(); rows=[]
        for p in self.catalog.get("produtos",[]):
            txt=f'{p.get("codigo_barras","")} {p.get("descricao","")} {p.get("grupo","")} {p.get("subclasse","")}'.upper()
            if (g=="Todos" or p.get("grupo")==g) and (s=="Todas" or p.get("subclasse")==s) and (not q or q in txt): rows.append(p)
        self.rows=rows; self.table.setRowCount(len(rows))
        for i,p in enumerate(rows):
            for j,v in enumerate([p.get("codigo_barras",""),p.get("descricao",""),p.get("grupo",""),p.get("subclasse","")]): self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
    def open_row(self,r,c):
        if r<len(self.rows): self.product_clicked.emit(self.rows[r])


# Visual rule for the explorer: subclasses and products are identified only by
# a vivid vertical neon bar; group icons remain untouched in the group cards.
NEON_SUBCLASS_COLORS = [
    "#00F5D4", "#00BBF9", "#7C3AED", "#FF2DAF", "#FFB000",
    "#39FF14", "#FF4D4D", "#00E5FF", "#B8FF00", "#FF6B00"
]

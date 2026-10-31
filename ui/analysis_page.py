from pathlib import Path
from PySide6.QtCore import Signal,QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QDateEdit,QPushButton,QLabel,QFrame,QScrollArea
from ui.window_chrome import get_open_file, show_message

from core.stores import STORES

class StoreRow(QFrame):
    remove=Signal(object)
    def __init__(self,index,parent=None):
        super().__init__(parent); self.setObjectName("Panel"); self.index=index
        l=QVBoxLayout(self); l.setContentsMargins(18,15,18,15); l.setSpacing(10)
        head=QHBoxLayout(); self.title=QLabel(f"STORE {index}"); self.title.setStyleSheet("font-size:14px;font-weight:900;color:#17326F;"); head.addWidget(self.title); head.addStretch(); x=QPushButton("Remove"); x.setObjectName("Danger"); x.clicked.connect(lambda:self.remove.emit(self)); head.addWidget(x); l.addLayout(head)
        form=QFormLayout(); self.loja=QComboBox(); self.loja.addItem("Select a store", "")
        for store in STORES: self.loja.addItem(store, store)
        self.stock=QLabel("No stock file selected"); self.sales=QLabel("No sales file selected")
        bs=QPushButton("Select stock file"); bs.setObjectName("Secondary"); bs.clicked.connect(self.pick_stock); bv=QPushButton("Select sales file"); bv.setObjectName("Secondary"); bv.clicked.connect(self.pick_sales)
        form.addRow("Store name",self.loja); form.addRow(bs,self.stock); form.addRow(bv,self.sales); l.addLayout(form); self.stock_path=None; self.sales_path=None
    def pick_stock(self):
        try:
            path = get_open_file(self, "Select stock file", "Spreadsheets (*.xlsx *.xls)")
        except Exception as error:
            show_message(self, "critical", "Could not open the file", str(error))
            return
        if path:
            self.stock_path = path
            self.stock.setText("✓ " + Path(path).name)

    def pick_sales(self):
        try:
            path = get_open_file(self, "Select sales file", "Spreadsheets (*.xlsx *.xls)")
        except Exception as error:
            show_message(self, "critical", "Could not open the file", str(error))
            return
        if path:
            self.sales_path = path
            self.sales.setText("✓ " + Path(path).name)

class AnalysisPage(QWidget):
    generate=Signal(dict)
    def __init__(self,parent=None,on_home=None):
        super().__init__(parent); self.rows=[]; root=QVBoxLayout(self); root.setContentsMargins(34,26,34,26); root.setSpacing(16)
        heading=QHBoxLayout(); back=QPushButton("← HOME"); back.setObjectName("Ghost"); back.clicked.connect(on_home or (lambda: None)); heading.addWidget(back); heading.addStretch()
        title=QLabel("New multi-store analysis"); title.setObjectName("Title"); heading.addWidget(title); heading.addStretch(); root.addLayout(heading); root.addWidget(QLabel(f"Select up to {len(STORES)} stores, each one once. The dashboard consolidates the data and lets you filter by store."))
        top=QFrame(); top.setObjectName("Panel"); f=QFormLayout(top); f.setContentsMargins(20,18,20,18)
        self.ini=QDateEdit(QDate.currentDate().addMonths(-1)); self.ini.setCalendarPopup(True); self.fim=QDateEdit(QDate.currentDate()); self.fim.setCalendarPopup(True)
        f.addRow("Period start",self.ini); f.addRow("Period end",self.fim); root.addWidget(top)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); inner=QWidget(); self.rows_layout=QVBoxLayout(inner); self.rows_layout.setContentsMargins(2,2,8,2); self.rows_layout.setSpacing(12); self.rows_layout.addStretch(); scroll.setWidget(inner); root.addWidget(scroll,1)
        actions=QHBoxLayout(); self.add_button=QPushButton("＋  ADD ANOTHER STORE"); self.add_button.setObjectName("AddStore"); self.add_button.clicked.connect(self.add_store); actions.addWidget(self.add_button); actions.addStretch(); gen=QPushButton("BUILD DASHBOARD"); gen.clicked.connect(self.submit); actions.addWidget(gen); root.addLayout(actions); self.add_store()
    def add_store(self):
        if len(self.rows)>=len(STORES): return
        row=StoreRow(len(self.rows)+1); row.remove.connect(self.remove_store); self.rows.append(row); self.rows_layout.insertWidget(max(0,self.rows_layout.count()-1),row)
        self.add_button.setEnabled(len(self.rows)<len(STORES))
    def remove_store(self,row):
        if len(self.rows)<=1:return
        self.rows.remove(row); row.deleteLater()
        for i,r in enumerate(self.rows,1): r.index=i; r.title.setText(f"STORE {i}")
        self.add_button.setEnabled(True)
    def submit(self):
        if self.ini.date()>self.fim.date(): show_message(self, "warning", "Invalid period","The start date cannot be after the end date."); return
        stores=[]
        for r in self.rows:
            loja=r.loja.currentData()
            if not loja or not r.stock_path or not r.sales_path:
                show_message(self, "warning", "Missing data","Fill in the store, stock file and sales file for every store."); return
            stores.append({"loja":loja,"estoque_path":r.stock_path,"vendas_path":r.sales_path})
        selected=[s["loja"] for s in stores]
        if len(selected)!=len(set(selected)):
            show_message(self, "warning", "Duplicate store","Select each store at most once."); return
        self.generate.emit({"lojas":stores,"data_inicio":self.ini.date().toPython(),"data_fim":self.fim.date().toPython()})

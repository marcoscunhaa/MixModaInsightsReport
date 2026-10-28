from PySide6.QtCore import Signal,QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QDateEdit,QPushButton,QLabel,QFileDialog,QMessageBox,QFrame,QScrollArea

STORES = ("Sitio São João", "Palmeiras", "Sapiranga", "Pedras")

class StoreRow(QFrame):
    remove=Signal(object)
    def __init__(self,index,parent=None):
        super().__init__(parent); self.setObjectName("Panel"); self.index=index
        l=QVBoxLayout(self); l.setContentsMargins(18,15,18,15); l.setSpacing(10)
        head=QHBoxLayout(); self.title=QLabel(f"LOJA {index}"); self.title.setStyleSheet("font-size:14px;font-weight:900;color:#17326F;"); head.addWidget(self.title); head.addStretch(); x=QPushButton("Remover"); x.setObjectName("Danger"); x.clicked.connect(lambda:self.remove.emit(self)); head.addWidget(x); l.addLayout(head)
        form=QFormLayout(); self.loja=QComboBox(); self.loja.addItem("Selecione uma loja", "")
        for store in STORES: self.loja.addItem(store, store)
        self.stock=QLabel("Nenhum estoque selecionado"); self.sales=QLabel("Nenhuma venda selecionada")
        bs=QPushButton("Selecionar estoque"); bs.setObjectName("Secondary"); bs.clicked.connect(self.pick_stock); bv=QPushButton("Selecionar vendas"); bv.setObjectName("Secondary"); bv.clicked.connect(self.pick_sales)
        form.addRow("Nome da loja",self.loja); form.addRow(bs,self.stock); form.addRow(bv,self.sales); l.addLayout(form); self.stock_path=None; self.sales_path=None
    def pick_stock(self):
        p,_=QFileDialog.getOpenFileName(self,"Selecionar estoque","","Planilhas (*.xlsx *.xls)")
        if p:self.stock_path=p; self.stock.setText("✓ "+p.split("/")[-1])
    def pick_sales(self):
        p,_=QFileDialog.getOpenFileName(self,"Selecionar vendas","","Planilhas (*.xlsx *.xls)")
        if p:self.sales_path=p; self.sales.setText("✓ "+p.split("/")[-1])

class AnalysisPage(QWidget):
    generate=Signal(dict)
    def __init__(self,parent=None,on_home=None):
        super().__init__(parent); self.rows=[]; root=QVBoxLayout(self); root.setContentsMargins(34,26,34,26); root.setSpacing(16)
        heading=QHBoxLayout(); back=QPushButton("← TELA INICIAL"); back.setObjectName("Ghost"); back.clicked.connect(on_home or (lambda: None)); heading.addWidget(back); heading.addStretch()
        title=QLabel("Nova análise multi-lojas"); title.setObjectName("Title"); heading.addWidget(title); heading.addStretch(); root.addLayout(heading); root.addWidget(QLabel("Selecione até 4 lojas, cada uma uma vez. O dashboard consolida os dados e permite filtrar por unidade."))
        top=QFrame(); top.setObjectName("Panel"); f=QFormLayout(top); f.setContentsMargins(20,18,20,18)
        self.ini=QDateEdit(QDate.currentDate().addMonths(-1)); self.ini.setCalendarPopup(True); self.fim=QDateEdit(QDate.currentDate()); self.fim.setCalendarPopup(True)
        f.addRow("Período inicial",self.ini); f.addRow("Período final",self.fim); root.addWidget(top)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); inner=QWidget(); self.rows_layout=QVBoxLayout(inner); self.rows_layout.setContentsMargins(2,2,8,2); self.rows_layout.setSpacing(12); self.rows_layout.addStretch(); scroll.setWidget(inner); root.addWidget(scroll,1)
        actions=QHBoxLayout(); self.add_button=QPushButton("＋  ADICIONAR OUTRA LOJA"); self.add_button.setObjectName("AddStore"); self.add_button.clicked.connect(self.add_store); actions.addWidget(self.add_button); actions.addStretch(); gen=QPushButton("GERAR DASHBOARD"); gen.clicked.connect(self.submit); actions.addWidget(gen); root.addLayout(actions); self.add_store()
    def add_store(self):
        if len(self.rows)>=len(STORES): return
        row=StoreRow(len(self.rows)+1); row.remove.connect(self.remove_store); self.rows.append(row); self.rows_layout.insertWidget(max(0,self.rows_layout.count()-1),row)
        self.add_button.setEnabled(len(self.rows)<len(STORES))
    def remove_store(self,row):
        if len(self.rows)<=1:return
        self.rows.remove(row); row.deleteLater()
        for i,r in enumerate(self.rows,1): r.index=i; r.title.setText(f"LOJA {i}")
        self.add_button.setEnabled(True)
    def submit(self):
        if self.ini.date()>self.fim.date(): QMessageBox.warning(self,"Período inválido","A data inicial não pode ser posterior à final."); return
        stores=[]
        for r in self.rows:
            loja=r.loja.currentData()
            if not loja or not r.stock_path or not r.sales_path:
                QMessageBox.warning(self,"Dados incompletos","Preencha loja, estoque e vendas de todas as lojas."); return
            stores.append({"loja":loja,"estoque_path":r.stock_path,"vendas_path":r.sales_path})
        selected=[s["loja"] for s in stores]
        if len(selected)!=len(set(selected)):
            QMessageBox.warning(self,"Loja repetida","Selecione cada loja no máximo uma vez."); return
        self.generate.emit({"lojas":stores,"data_inicio":self.ini.date().toPython(),"data_fim":self.fim.date().toPython()})

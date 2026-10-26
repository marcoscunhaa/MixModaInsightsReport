from utils.formatting import br_number
import json
from PySide6.QtWidgets import QMainWindow,QStackedWidget,QWidget,QVBoxLayout,QLabel,QPushButton,QMessageBox,QHBoxLayout
from ui.analysis_page import AnalysisPage
from ui.dashboard_page import DashboardPage
from ui.catalog_page import CatalogPage
from ui.styles import APP_QSS
from core.loader import load_stock,load_sales
from core.matcher import build_analysis, load_classification
from core.catalog_store import load_catalog, load_classification_from_catalog
from core.models import AnalysisConfig
import pandas as pd
import traceback
class MainWindow(QMainWindow):
    def __init__(self,catalog_path):
        super().__init__(); self.setWindowTitle("Mix Moda Insights"); self.resize(1580,980); self.setStyleSheet(APP_QSS)
        # JSON único: o mesmo arquivo alimenta o catálogo e a classificação por loja + código + descrição.
        self.catalog=load_catalog(catalog_path)
        self.classification = load_classification_from_catalog(self.catalog, load_classification)
        self.stack=QStackedWidget(); self.setCentralWidget(self.stack); self.home=self.home_page(); self.analysis=AnalysisPage(); self.analysis.generate.connect(self.generate)
        self.stack.addWidget(self.home); self.stack.addWidget(self.analysis)
    def home_page(self):
        w=QWidget(); w.setObjectName("Shell"); l=QVBoxLayout(w); l.setContentsMargins(90,80,90,70); l.setSpacing(16)
        badge=QLabel("MIX MODA  •  INTELLIGENCE"); badge.setStyleSheet("color:#2854D9;font-weight:900;font-size:12px;letter-spacing:2px;")
        l.addWidget(badge); t=QLabel("MIX MODA INSIGHTS"); t.setObjectName("Title"); l.addWidget(t)
        s=QLabel("Uma central executiva para entender estoque, vendas, giro, ruptura e performance por loja."); s.setObjectName("Subtitle"); l.addWidget(s)
        row=QHBoxLayout(); b=QPushButton("CRIAR NOVA ANÁLISE  →"); b.clicked.connect(lambda:self.stack.setCurrentWidget(self.analysis)); row.addWidget(b); c=QPushButton("EXPLORAR CATÁLOGO"); c.setObjectName("Secondary"); c.clicked.connect(self.open_catalog); row.addWidget(c); row.addStretch(); l.addLayout(row); l.addStretch()
        m=self.catalog.get("meta",{}); foot=QLabel(f"Catálogo oficial • {br_number(m.get('total_produtos_unicos_por_codigo',0),0)} códigos • {m.get('total_grupos',0)} grupos • {m.get('total_subclasses',0)} subclasses"); foot.setObjectName("Muted"); l.addWidget(foot); return w
    def open_catalog(self):
        if not hasattr(self,"catpage"): self.catpage=CatalogPage(self.catalog); self.stack.addWidget(self.catpage)
        self.stack.setCurrentWidget(self.catpage)
    def generate(self,info):
        try:
            frames=[]; audits=[]
            for s in info["lojas"]:
                stock,sales=load_stock(s["estoque_path"]),load_sales(s["vendas_path"])
                cfg=AnalysisConfig(loja=s["loja"],data_inicio=info["data_inicio"],data_fim=info["data_fim"],estoque_path=s["estoque_path"],vendas_path=s["vendas_path"])
                df,audit=build_analysis(stock,sales,self.catalog,s["loja"],cfg,self.classification); frames.append(df); audits.append(audit)
            df=pd.concat([x for x in frames if not x.empty],ignore_index=True) if any(not x.empty for x in frames) else pd.DataFrame()
            if df.empty: QMessageBox.warning(self,"Sem dados","Nenhum produto válido permaneceu após limpeza e cruzamento."); return
            audit={k:sum(a.get(k,0) for a in audits) for k in set().union(*(a.keys() for a in audits))}
            page=DashboardPage(df,(info["data_inicio"],info["data_fim"]),audit); self.stack.addWidget(page); self.stack.setCurrentWidget(page)
        except Exception as e:
            details = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Erro ao gerar análise",
                f"Não foi possível processar os arquivos.\n\n{type(e).__name__}: {e}\n\n"
                "Verifique se os arquivos são XLS/XLSX válidos e se seguem o layout da Mix Moda."
            )
            print(details)

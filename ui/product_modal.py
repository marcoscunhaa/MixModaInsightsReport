from utils.formatting import brl, br_number
from PySide6.QtWidgets import QDialog,QVBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QHBoxLayout,QWidget
from PySide6.QtCore import Qt

class ProductModal(QDialog):
    def __init__(self,row,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalhes do Produto")
        self.resize(920,720)
        self.setMinimumSize(860,680)
        self.setStyleSheet("""
            QDialog{background:#EEF2FF;}
            QLabel{color:#24324A;background:transparent;}
            QFrame#hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4B2E83,stop:0.55 #7C3AED,stop:1 #E85D8A);border-radius:22px;border:0px;}
            QFrame#metric{background:#FFFFFF;border:1px solid #E1DDF2;border-radius:16px;}
            QFrame#metric:hover{border:1px solid #B9A2F2;background:#FBF9FF;}
            QFrame#section{background:#F8F7FF;border:1px solid #DCD6F7;border-radius:18px;}
            QLabel#eyebrow{background:transparent;color:#EDE7FF;font-size:11px;font-weight:700;letter-spacing:1px;}
            QLabel#productTitle{background:transparent;color:#FFFFFF;font-size:25px;font-weight:850;}
            QLabel#meta{background:transparent;color:#F5EEFF;font-size:12px;}
            QLabel#metricLabel{color:#7A8498;font-size:10px;font-weight:700;}
            QLabel#metricValue{color:#24324A;font-size:19px;font-weight:850;}
            QLabel#sectionTitle{color:#24324A;font-size:14px;font-weight:850;}
            QLabel#insight{background:#F1ECFF;border-left:5px solid #8B5CF6;border-radius:10px;color:#394862;font-size:12px;padding:12px;}
            QPushButton#close{background:#24324A;color:#FFFFFF;border:none;border-radius:11px;padding:11px 26px;font-weight:750;}
            QPushButton#close:hover{background:#3A4B68;}
        """)
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,18); root.setSpacing(14)

        hero=QFrame(); hero.setObjectName("hero")
        hl=QVBoxLayout(hero); hl.setContentsMargins(22,20,22,20); hl.setSpacing(6)
        e=QLabel("VISÃO COMPLETA DO PRODUTO"); e.setObjectName("eyebrow"); hl.addWidget(e)
        title=QLabel(str(row.get("descricao", "Produto sem descrição"))); title.setObjectName("productTitle"); title.setWordWrap(True); hl.addWidget(title)
        meta=QLabel(f"Código  {row.get('codigo_barras','—')}   •   {row.get('grupo','—')}   •   {row.get('subclasse','—')}   •   {row.get('loja','—')}"); meta.setObjectName("meta"); meta.setWordWrap(True); hl.addWidget(meta)
        root.addWidget(hero)

        body=QWidget(); body.setObjectName("productBody"); body.setStyleSheet("QWidget#productBody{background:#F3F0FF;border:1px solid #DDD5FA;border-radius:22px;}"); bl=QVBoxLayout(body); bl.setContentsMargins(14,14,14,16); bl.setSpacing(14)

        metrics=QGridLayout(); metrics.setHorizontalSpacing(12); metrics.setVerticalSpacing(12)
        fields=[
            ("ESTOQUE ATUAL",br_number(row.get("quantidade_estoque",0),0),"#7C3AED"),
            ("VENDAS NO PERÍODO",br_number(row.get("quantidade_vendida",0),0),"#E85D8A"),
            ("FATURAMENTO",brl(row.get('valor_vendido',0)),"#E85D8A"),
            ("VALOR EM ESTOQUE",brl(row.get('valor_estoque',0)),"#F3B63F"),
            ("PREÇO DE COMPRA",brl(row.get('preco_compra',0)),"#36A269"),
            ("PREÇO DE VENDA",brl(row.get('preco_venda',0)),"#2C9FD6"),
            ("MARGEM UNITÁRIA",brl(row.get('margem_unitaria',0)),"#36A269"),
            ("MARGEM %",f"{row.get('margem_percentual',0):.1f}%","#7C3AED"),
            ("GIRO DO PERÍODO",f"{row.get('giro',0):.1f}%","#2C9FD6"),
            ("STATUS",str(row.get('status_estoque','—')),"#D9284B"),
        ]
        for i,(k,v,c) in enumerate(fields):
            box=QFrame(); box.setObjectName("metric"); box.setStyleSheet(f"QFrame#metric{{background:#FFFFFF;border:1px solid #E6EAF2;border-radius:16px;border-top:4px solid {c};}} QFrame#metric:hover{{background:#FCFAFF;border:1px solid #D8CFF0;border-top:4px solid {c};}}")
            q=QVBoxLayout(box); q.setContentsMargins(14,11,14,12); q.setSpacing(4)
            a=QLabel(k); a.setObjectName("metricLabel"); q.addWidget(a)
            z=QLabel(v); z.setObjectName("metricValue"); q.addWidget(z)
            metrics.addWidget(box,i//3,i%3)
        bl.addLayout(metrics)

        section=QFrame(); section.setObjectName("section"); sl=QVBoxLayout(section); sl.setContentsMargins(16,15,16,16); sl.setSpacing(8)
        st=QLabel("LEITURA DOS INDICADORES"); st.setObjectName("sectionTitle"); sl.addWidget(st)
        q=row.get("quantidade_estoque",0); v=row.get("quantidade_vendida",0)
        msg=("Produto vendeu no período e está com estoque baixo, indicando atenção para reposição." if v>0 and q<=3 else
             "Produto possui estoque, mas não apresentou vendas no período." if q>0 and v==0 else
             "Os indicadores não apontam um alerta específico pelas regras configuradas.")
        ins=QLabel(msg); ins.setObjectName("insight"); ins.setWordWrap(True); sl.addWidget(ins)
        bl.addWidget(section)
        bl.addStretch(1)
        root.addWidget(body,1)

        bottom=QHBoxLayout(); bottom.addStretch(1); b=QPushButton("Fechar"); b.setObjectName("close"); b.clicked.connect(self.accept); bottom.addWidget(b); root.addLayout(bottom)

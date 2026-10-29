from utils.formatting import brl, br_number
from PySide6.QtWidgets import QDialog,QVBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QHBoxLayout,QWidget
from PySide6.QtCore import Qt
from ui.window_chrome import install_mac_window_chrome

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
        root=QVBoxLayout(self); root.setContentsMargins(12,8,12,12); root.setSpacing(14); install_mac_window_chrome(self,root)

        hero=QFrame(); hero.setObjectName("hero")
        hl=QVBoxLayout(hero); hl.setContentsMargins(22,20,22,20); hl.setSpacing(6)
        e=QLabel("VISÃO COMPLETA DO PRODUTO"); e.setObjectName("eyebrow"); hl.addWidget(e)
        description=str(row.get("descricao", "Produto sem descrição"))
        barcode=str(row.get("codigo_barras", "")).strip()
        title=QLabel(description); title.setObjectName("productTitle"); title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); hl.addWidget(title)
        barcode_label=QLabel(f"Código  {barcode or '—'}"); barcode_label.setObjectName("meta")
        barcode_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); hl.addWidget(barcode_label)
        meta=QLabel(f"{row.get('grupo','—')}   •   {row.get('subclasse','—')}   •   {row.get('loja','—')}"); meta.setObjectName("meta"); meta.setWordWrap(True); hl.addWidget(meta)
        root.addWidget(hero)

        body=QWidget(); body.setObjectName("productBody"); body.setStyleSheet("QWidget#productBody{background:#F3F0FF;border:1px solid #DDD5FA;border-radius:22px;}"); bl=QVBoxLayout(body); bl.setContentsMargins(14,14,14,16); bl.setSpacing(14)

        metrics=QGridLayout(); metrics.setHorizontalSpacing(12); metrics.setVerticalSpacing(12)
        price_tiers=[t for t in (row.get("precos_venda") or []) if isinstance(t,dict)]
        many_prices=len(price_tiers)>1
        if many_prices: self.resize(920,820)
        fields=[
            ("ESTOQUE ATUAL",br_number(row.get("quantidade_estoque",0),0),"#7C3AED"),
            ("VENDAS NO PERÍODO",br_number(row.get("quantidade_vendida",0),0),"#E85D8A"),
            ("FATURAMENTO",brl(row.get('valor_vendido',0)),"#E85D8A"),
            ("VALOR EM ESTOQUE",brl(row.get('valor_estoque',0)),"#F3B63F"),
            ("PREÇO DE COMPRA",brl(row.get('preco_compra',0)),"#36A269"),
            ("PREÇO DE VENDA MÉDIO" if many_prices else "PREÇO DE VENDA",brl(row.get('preco_venda',0)),"#2C9FD6"),
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
        if many_prices:
            bl.addWidget(self._price_tiers(price_tiers))

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

    def _price_tiers(self,tiers):
        """Vendas do período separadas por preço de venda, com o total no fim."""
        section=QFrame(); section.setObjectName("section"); sl=QVBoxLayout(section); sl.setContentsMargins(16,14,16,14); sl.setSpacing(6)
        st=QLabel("VALORES DE VENDA NO PERÍODO"); st.setObjectName("sectionTitle"); sl.addWidget(st)
        hint=QLabel("O produto foi vendido por mais de um preço. O faturamento é a soma de cada preço × quantidade.")
        hint.setStyleSheet("color:#7A8498;font-size:11px;"); hint.setWordWrap(True); sl.addWidget(hint)
        grid=QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(6)
        for col,(text,align) in enumerate((("PREÇO",Qt.AlignmentFlag.AlignLeft),("QUANTIDADE",Qt.AlignmentFlag.AlignRight),("FATURAMENTO",Qt.AlignmentFlag.AlignRight))):
            h=QLabel(text); h.setObjectName("metricLabel"); grid.addWidget(h,0,col,align)
        total_qty=0; total_revenue=0
        for i,t in enumerate(tiers,1):
            qty=float(t.get("quantidade",0)); revenue=float(t.get("faturamento",0)); total_qty+=qty; total_revenue+=revenue
            price=QLabel(brl(t.get("preco_venda",0))); price.setStyleSheet("color:#2C9FD6;font-size:14px;font-weight:850;")
            amount=QLabel(f"{br_number(qty,0)} un."); amount.setStyleSheet("color:#24324A;font-size:13px;font-weight:700;")
            value=QLabel(brl(revenue)); value.setStyleSheet("color:#24324A;font-size:13px;font-weight:800;")
            grid.addWidget(price,i,0,Qt.AlignmentFlag.AlignLeft); grid.addWidget(amount,i,1,Qt.AlignmentFlag.AlignRight); grid.addWidget(value,i,2,Qt.AlignmentFlag.AlignRight)
        line=QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#DCD6F7;"); grid.addWidget(line,len(tiers)+1,0,1,3)
        for col,(text,align) in enumerate((("TOTAL",Qt.AlignmentFlag.AlignLeft),(f"{br_number(total_qty,0)} un.",Qt.AlignmentFlag.AlignRight),(brl(total_revenue),Qt.AlignmentFlag.AlignRight))):
            x=QLabel(text); x.setStyleSheet("color:#E85D8A;font-size:13px;font-weight:900;"); grid.addWidget(x,len(tiers)+2,col,align)
        grid.setColumnStretch(0,1); sl.addLayout(grid)
        return section

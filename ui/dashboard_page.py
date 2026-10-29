from utils.formatting import brl, br_number
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QLineEdit,QLabel,QTableWidget,
    QTableWidgetItem,QScrollArea,QGridLayout,QFrame,QPushButton,QHeaderView,QDialog,
    QListWidget,QListWidgetItem,QAbstractItemView)
from PySide6.QtGui import QColor, QFont
from ui.widgets import Card, KpiCard, RankCard, StatusFilterBar
from core.kpi_view import STATUS_OPTIONS, kpi_cards, status_counts
from ui.product_modal import ProductModal
from charts.dashboard_charts import make_chart
from core.analyzer import filter_analysis,kpis,single_product_labels,stock_by_store,top_sold,stagnant,critical,rupture
from core.insights import generate_insights
from utils.normalization import normalize_barcode, normalize_text
from exports.pdf_export import export_dashboard_pdf
from ui.stock_alerts import StockAlertsDialog
from ui.window_chrome import get_save_file, install_mac_window_chrome, show_message

SUBCLASS_EMOJIS = ["👗","👚","👕","👖","👟","🥿","👜","💄","💍","🧸","🏠","🛏️","🍳","🧴","🧢","🩱","🩴","🎀","🧦","🧺"]
SUBCLASS_COLORS = ["#5B6CFF","#E85D8A","#00A88F","#FFB52E","#19A9C7","#8B6FE8","#FF7A59","#D94D9A","#36A269","#F06A9B","#4B8EF7","#12B8A6"]

def _stable_color(text):
    return SUBCLASS_COLORS[sum(ord(c) for c in str(text)) % len(SUBCLASS_COLORS)]

def _rgba(hex_color, alpha):
    # Qt interpreta #RRGGBBAA como #AARRGGBB; por isso usamos rgba() para controlar a opacidade corretamente.
    h=hex_color.lstrip("#"); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

def _emoji(text, idx=0):
    t=str(text).upper()
    rules=[("PIJ", "👕"),("CALÇ", "👟"),("CALC", "👟"),("CHIN", "🩴"),("COSM", "💄"),("BIJ", "💍"),("BRIN", "🧸"),("BOLSA", "👜"),("ACESS", "👜"),("ROUP", "👗"),("VEST", "👗"),("CAMA", "🛏️"),("MESA", "🍽️"),("BANHO", "🛁"),("UTIL", "🏠"),("PESS", "🧴"),("PRAIA", "🩱"),("INF", "🧸")]
    for key,emo in rules:
        if key in t: return emo
    return SUBCLASS_EMOJIS[idx % len(SUBCLASS_EMOJIS)]

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

class HierarchyExplorer(QDialog):
    def __init__(self, df, start_group=None, parent=None):
        super().__init__(parent); self.df=df.copy(); self.path=[]
        self.setWindowTitle("Explorador de Produtos • Mix Moda Insights"); self.resize(1180,720)
        root=QVBoxLayout(self); root.setContentsMargins(12,8,12,12); root.setSpacing(12); install_mac_window_chrome(self,root)
        head=QHBoxLayout(); titlebox=QVBoxLayout(); self.title=QLabel("Explorador de catálogo"); self.title.setStyleSheet("font-size:24px;font-weight:900;color:#12213D;"); titlebox.addWidget(self.title)
        self.crumb=QLabel(""); self.crumb.setStyleSheet("color:#64728A;font-size:12px;font-weight:800;"); titlebox.addWidget(self.crumb); head.addLayout(titlebox); head.addStretch()
        self.back=QPushButton("← Voltar"); self.back.setObjectName("Ghost"); self.back.clicked.connect(self.go_back); head.addWidget(self.back); root.addLayout(head)
        self.list=QListWidget(); self.list.setViewMode(QListWidget.IconMode); self.list.setResizeMode(QListWidget.Adjust); self.list.setSpacing(10); self.list.setGridSize(QSize(350,116)); self.list.setUniformItemSizes(False); self.list.itemClicked.connect(self.open_item); root.addWidget(self.list,1)
        self.render_group(start_group) if start_group else self.render_groups()

    def _add_card(self,title,subtitle,value,key,kind,accent,emoji):
        item=QListWidgetItem(); item.setData(Qt.UserRole,(kind,key)); item.setSizeHint(QSize(340,104)); self.list.addItem(item)
        self.list.setItemWidget(item, ExplorerCard(emoji,title,subtitle,value,accent,flat=True))

    def render_groups(self):
        self.path=[]; self.crumb.setText("Todos os grupos"); self.title.setText("Explorador • Grupos"); self.list.clear(); self.back.setEnabled(False)
        g=self.df.groupby("grupo",dropna=False).agg(produtos=("codigo_barras","count"),vendas=("quantidade_vendida","sum"),estoque=("quantidade_estoque","sum")).reset_index()
        g["_ord"] = g["grupo"].map(lambda x: normalize_text(x))
        g=g.sort_values("_ord",kind="stable")
        for i,r in g.iterrows():
            name=str(r.grupo); self._add_card(name,f"{br_number(r.produtos,0)} produtos",f"{br_number(r.vendas,0)} vendas",name,"group",_stable_color(name),"")

    def render_group(self,g):
        self.path=[("group",g)]; self.crumb.setText(f"Todos os grupos  ›  {g}"); self.title.setText(f"{g} • Subclasses"); self.list.clear(); self.back.setEnabled(True)
        d=self.df[self.df.grupo==g]; x=d.groupby("subclasse",dropna=False).agg(produtos=("codigo_barras","count"),vendas=("quantidade_vendida","sum"),estoque=("quantidade_estoque","sum")).reset_index()
        x["_nome"] = x["subclasse"].map(lambda v: "Sem subclasse" if str(v)=="nan" else str(v))
        x["_ord"] = x["_nome"].map(normalize_text); x=x.sort_values("_ord",kind="stable")
        for i,r in x.iterrows():
            sub=r["_nome"]; self._add_card(sub,f"{br_number(r.produtos,0)} produtos",f"{br_number(r.vendas,0)} vendas  •  {br_number(r.estoque,0)} em estoque",sub,"sub",_stable_color(sub),"")

    def render_sub(self,g,sub):
        self.path=[("group",g),("sub",sub)]; self.crumb.setText(f"Todos os grupos  ›  {g}  ›  {sub}"); self.title.setText(f"Produtos • {sub}"); self.list.clear()
        d=self.df[(self.df.grupo==g)&(self.df.subclasse==sub)].copy()
        d["_ord"] = d["descricao"].map(normalize_text); d=d.sort_values(["_ord","codigo_barras"],kind="stable")
        for i,(_,r) in enumerate(d.iterrows()):
            accent=_stable_color(str(r.descricao)); self._add_card(str(r.descricao),f"{r.codigo_barras}  •  {r.loja}",f"{br_number(r.quantidade_vendida,0)} vendas  •  {brl(r.valor_vendido)}",r.to_dict(),"product",accent,"")

    def open_item(self,item):
        kind,key=item.data(Qt.UserRole)
        if kind=="group": self.render_group(key)
        elif kind=="sub": self.render_sub(self.path[0][1],key)
        elif kind=="product": ProductModal(key,self).exec()
    def go_back(self):
        if len(self.path)==2: self.render_group(self.path[0][1])
        elif len(self.path)==1: self.render_groups()

class DashboardPage(QWidget):
    def __init__(self,df,period,audit,parent=None,on_home=None,alert_store=None):
        super().__init__(parent); self.df=df; self.period=period; self.audit=audit; self.alert_store=alert_store
        root=QVBoxLayout(self); root.setContentsMargins(28,18,28,22); root.setSpacing(12)
        head=QHBoxLayout(); brand=QVBoxLayout(); title=QLabel("MIX MODA INSIGHTS"); title.setObjectName("Title"); brand.addWidget(title); brand.addWidget(QLabel("Central executiva de estoque, vendas, faturamento e rotação por loja")); head.addLayout(brand); head.addStretch();
        if on_home:
            home_button=QPushButton("← INÍCIO"); home_button.setObjectName("Ghost"); home_button.clicked.connect(on_home); head.addWidget(home_button)
        self.alert_button=QPushButton()
        self.alert_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.alert_button.clicked.connect(self.open_stock_alerts)
        head.addWidget(self.alert_button)
        pdf=QPushButton("EXPORTAR PDF"); pdf.clicked.connect(self.export_pdf); head.addWidget(pdf); root.addLayout(head)
        filters=QFrame(); filters.setObjectName("Panel"); fbox=QVBoxLayout(filters); fbox.setContentsMargins(12,10,12,10); fbox.setSpacing(10); fl=QHBoxLayout(); fl.setSpacing(8); fbox.addLayout(fl)
        self.store=QComboBox(); self.store.addItem("Todas as lojas"); self.store.addItems(sorted(df.loja.dropna().unique())); self.group=QComboBox(); self.group.addItem("Todos os grupos"); self.group.addItems(sorted(df.grupo.dropna().unique())); self.sub=QComboBox(); self.sub.addItem("Todas as subclasses"); self.status=StatusFilterBar(STATUS_OPTIONS); self.search=QLineEdit(); self.search.setPlaceholderText("Buscar produto, código, grupo ou subclasse...")
        for w in (self.store,self.group,self.sub,self.search): fl.addWidget(w)
        fl.setStretch(3,1); fbox.addWidget(self.status)
        root.addWidget(filters)
        sc=QScrollArea(); sc.setWidgetResizable(True); inner=QWidget(); self.body=QVBoxLayout(inner); self.body.setContentsMargins(0,0,6,0); self.body.setSpacing(14); sc.setWidget(inner); root.addWidget(sc,1)
        self.store.currentTextChanged.connect(self.refresh); self.group.currentTextChanged.connect(self.refresh); self.sub.currentTextChanged.connect(self.refresh); self.status.currentTextChanged.connect(self.refresh); self.search.textChanged.connect(self.refresh); self.refresh()

    def _filtered_alerts(self):
        if not self.alert_store:
            return []
        snapshot = self.alert_store.load_snapshot()
        alerts = self.alert_store.evaluate(snapshot.get("rows", []))
        visible = {
            (
                normalize_barcode(row.codigo_barras),
                normalize_text(row.descricao),
                normalize_text(row.loja),
            )
            for row in self.current_df().itertuples(index=False)
        }
        return [
            alert for alert in alerts
            if (
                normalize_barcode(alert.get("codigo_barras")),
                normalize_text(alert.get("descricao")),
                normalize_text(alert.get("loja")),
            ) in visible
        ]

    def refresh_alert_button(self):
        alerts = self._filtered_alerts()
        count = len(alerts)
        self.alert_button.setText(f"🔔  ALERTAS  ·  {count}")
        self.alert_button.setStyleSheet(
            "QPushButton{background:#FFF0F1;color:#BD3049;border:1px solid #F0B7C0;"
            "border-radius:12px;padding:10px 15px;font-weight:900;}"
            "QPushButton:hover{background:#FFE1E5;border-color:#E98A98;}"
            if count else
            "QPushButton{background:#F1F4FA;color:#556782;border:1px solid #DCE4EF;"
            "border-radius:12px;padding:10px 15px;font-weight:900;}"
            "QPushButton:hover{background:#E8EEF8;}"
        )
        self.alert_button.setToolTip(
            f"{count} produto(s) atingiram suas regras de estoque."
            if count else "Nenhum produto atingiu suas regras de estoque."
        )

    def open_stock_alerts(self):
        StockAlertsDialog(self._filtered_alerts(), self).exec()

    def current_df(self):
        status="Todos" if self.status.currentText()=="Todos os status" else self.status.currentText(); return filter_analysis(self.df,*self._base_filters(),status)
    def _base_filters(self):
        loja="Todas" if self.store.currentText()=="Todas as lojas" else self.store.currentText(); grupo="Todos" if self.group.currentText()=="Todos os grupos" else self.group.currentText(); sub="Todas" if self.sub.currentText()=="Todas as subclasses" else self.sub.currentText()
        return loja,grupo,sub,self.search.text()
    def clear_body(self):
        while self.body.count():
            item=self.body.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    z=item.layout().takeAt(0)
                    if z.widget(): z.widget().deleteLater()
    def refresh(self):
        options=self.df
        if self.store.currentText()!="Todas as lojas":
            options=options[options.loja==self.store.currentText()]
        old_group=self.group.currentText()
        groups=sorted(options.grupo.dropna().unique())
        self.group.blockSignals(True); self.group.clear(); self.group.addItem("Todos os grupos"); self.group.addItems(groups)
        self.group.setCurrentText(old_group if old_group in [self.group.itemText(i) for i in range(self.group.count())] else "Todos os grupos"); self.group.blockSignals(False)
        if self.group.currentText()!="Todos os grupos":
            options=options[options.grupo==self.group.currentText()]
        old_sub=self.sub.currentText()
        subclasses=sorted(options.subclasse.dropna().unique())
        self.sub.blockSignals(True); self.sub.clear(); self.sub.addItem("Todas as subclasses"); self.sub.addItems(subclasses)
        self.sub.setCurrentText(old_sub if old_sub in [self.sub.itemText(i) for i in range(self.sub.count())] else "Todas as subclasses"); self.sub.blockSignals(False)
        # Contagem de cada status com os outros filtros aplicados (sem o de status).
        self.status.set_counts(status_counts(filter_analysis(self.df,*self._base_filters(),"Todos")))
        d=self.current_df(); self.refresh_alert_button(); self.clear_body(); grid=QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(12)
        for i,spec in enumerate(kpi_cards(d)):
            c=KpiCard(spec["label"],spec["value"],spec["hint"],spec["accent"],spec["emoji"],spec["tone"],spec["clickable"])
            if spec["clickable"]: c.clicked.connect(lambda name=spec["key"]:self.detail(name,d))
            grid.addWidget(c,i//5,i%5)
        self.body.addLayout(grid)
        row1=QHBoxLayout(); row1.setSpacing(12); row1.addWidget(self.panel("TOP 3 MAIS VENDIDOS NA ANÁLISE",self.top3(d)),1); row1.addWidget(self.panel("RANKING POR LOJA",self.store_ranking(d)),1); self.body.addLayout(row1)
        charts=QGridLayout(); charts.setSpacing(12)
        for i,k in enumerate(["grupo_valor_3d","grupo_pizza","vendas_3d","rotacao","status","estoque_x_vendas"]): charts.addWidget(self.chart_panel(make_chart(k,d)),i//2,i%2)
        self.body.addLayout(charts)
        self.body.addWidget(self.section_label("EXPLORADOR DINÂMICO — GRUPO › SUBCLASSE › PRODUTO")); self.pivot_table(d)
        self.body.addWidget(self.section_label("PRODUTOS MAIS VENDIDOS")); self.table_section(top_sold(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_vendida","valor_vendido","giro"],150,"#2F5BEA")
        self.body.addWidget(self.section_label("ESTOQUE PARADO / CAPITAL PRESO")); self.table_section(stagnant(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_estoque","valor_estoque"],150,"#FF9F43")
        self.body.addWidget(self.section_label("PRODUTOS CRÍTICOS")); self.table_section(critical(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_estoque","quantidade_vendida","status_estoque"],160,"#E94B5F",critical_mode=True)
        ins=QFrame(); ins.setObjectName("Panel"); il=QVBoxLayout(ins); il.setContentsMargins(16,14,16,14); il.addWidget(self.section_label("INSIGHTS INTELIGENTES"))
        insight_colors=[("#5B6CFF","💡"),("#00A88F","📈"),("#FF9F43","⚠️"),("#E85D8A","🎯")]  # azul, verde, laranja, rosa (mesma cor do título de cada insight)
        for idx,x in enumerate(generate_insights(d)):
            accent,emoji=insight_colors[idx%len(insight_colors)]
            # Contorno propositalmente discreto: o destaque fica no conteúdo, não na borda.
            # A regra de borda é restrita ao card (#InsightCard) para não vazar para os QLabel filhos.
            r=QFrame(); r.setObjectName("InsightCard"); r.setStyleSheet(f"QFrame#InsightCard{{background:#FFFFFF;border:1px solid {_rgba(accent,0.45)};border-radius:14px;}} QLabel{{border:none;background:transparent;}} QLabel#it{{color:{accent};font-size:12px;font-weight:900;}} QLabel#ix{{color:#40516E;font-size:11px;font-weight:700;}}")
            rl=QHBoxLayout(r); rl.setContentsMargins(12,10,12,10); icon=QLabel(emoji); icon.setStyleSheet(f"font-size:21px;color:{accent};background:transparent;"); rl.addWidget(icon); box=QVBoxLayout(); a=QLabel(x['titulo']); a.setObjectName("it"); box.addWidget(a); b=QLabel(x['texto']); b.setObjectName("ix"); b.setWordWrap(True); box.addWidget(b); rl.addLayout(box,1); il.addWidget(r)
        self.body.addWidget(ins); audit=QLabel(f"Auditoria: {br_number(self.audit.get('produtos_estoque',0),0)} itens de estoque • {br_number(self.audit.get('produtos_vendas',0),0)} itens de vendas • {br_number(self.audit.get('vendas_correspondentes',0),0)} correspondências • {br_number(self.audit.get('vendas_sem_correspondencia',0),0)} vendas ignoradas"); audit.setStyleSheet("color:#7A879D;font-size:10px;font-weight:700;padding:5px;"); self.body.addWidget(audit)

    def section_label(self,text): x=QLabel(text); x.setObjectName("SectionTitle"); return x
    def panel(self,title,widget): f=QFrame(); f.setObjectName("Panel"); l=QVBoxLayout(f); l.setContentsMargins(16,14,16,14); l.addWidget(self.section_label(title)); l.addWidget(widget); return f
    def chart_panel(self,chart): f=QFrame(); f.setObjectName("Panel"); l=QVBoxLayout(f); l.setContentsMargins(8,6,8,6); l.addWidget(chart); return f
    def top3(self,d):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,4,0,0); rows=top_sold(d,3).reset_index(drop=True); medals=[("👑","#F3B63F"),("🥈","#6D7A91"),("🥉","#B97845")]
        for i,r in rows.iterrows(): c=RankCard(medals[i][0],r.descricao,r.quantidade_vendida,medals[i][1],r.valor_vendido); c.clicked.connect(lambda rr=r:self.open_row_dict(rr.to_dict())); l.addWidget(c)
        l.addStretch(); return w
    def store_ranking(self,d):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,4,0,0); x=d.groupby("loja",as_index=False).agg(vendas=("quantidade_vendida","sum"),faturamento=("valor_vendido","sum")).sort_values("vendas",ascending=False).head(5)
        for i,(_,r) in enumerate(x.iterrows()): c=RankCard(str(i+1),r.loja,r.vendas,["#2854D9","#16B8C8","#0F9D8A","#7C6FE6","#E85D8A"][i%5],r.faturamento); l.addWidget(c)
        l.addStretch(); return w
    def pivot_table(self,d):
        g=d.groupby("grupo",as_index=False).agg(produtos=("codigo_barras","count"),estoque=("quantidade_estoque","sum"),vendas=("quantidade_vendida","sum"),valor_estoque=("valor_estoque","sum"),faturamento=("valor_vendido","sum"),giro=("giro","mean")).sort_values("vendas",ascending=False)
        t=QTableWidget(len(g),7); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setMinimumHeight(max(225, 44 + len(g)*38)); t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); t.setHorizontalHeaderLabels(["Grupo","Produtos","Estoque","Vendas","Valor estoque","Faturamento","Giro (%)"]); t.verticalHeader().setVisible(False); t.setSelectionBehavior(QTableWidget.SelectRows); t.setAlternatingRowColors(True); t.setSortingEnabled(False); rows=list(g.iterrows()); palette=["#EEF3FF","#E8FBF7","#FFF3E2","#F4EEFF","#FFEAF1"]
        for i,(_,r) in enumerate(rows):
            vals=[r.grupo,r.produtos,r.estoque,r.vendas,r.valor_estoque,r.faturamento,r.giro]
            for j,v in enumerate(vals):
                if j in (4,5): txt=brl(v)
                elif j==6: txt=f"{v:.1f}%"
                elif isinstance(v,float): txt=br_number(v,0)
                else: txt=str(v)
                item=QTableWidgetItem(txt); item.setBackground(QColor(palette[i%len(palette)])); item.setForeground(QColor("#17326F")); t.setItem(i,j,item)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); t.horizontalHeader().setStretchLastSection(True); t.cellClicked.connect(lambda rr,cc,rs=rows:self.open_group(rs,rr)); self.body.addWidget(t)
    def open_group(self,rows,r):
        if 0<=r<len(rows): HierarchyExplorer(self.current_df(),str(rows[r][1]["grupo"]),self).exec()
    def table_section(self,d,cols,height=140,accent="#2F5BEA",critical_mode=False):
        t=QTableWidget(len(d),len(cols)); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setMinimumHeight(max(height, 44 + len(d)*38)); t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); t.setAlternatingRowColors(True); t.setSortingEnabled(False); t.setHorizontalHeaderLabels([c.replace("_"," ").title() for c in cols]); t.horizontalHeader().setStretchLastSection(True); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); t.verticalHeader().setVisible(False); t.setSelectionBehavior(QTableWidget.SelectRows); rows=list(d.iterrows())
        t.setStyleSheet(f"QTableWidget{{border:1px solid {accent}55;border-radius:14px;gridline-color:#E9EEF5;alternate-background-color:#FAFCFF;}} QHeaderView::section{{background:{accent};color:white;border:none;padding:10px;font-weight:900;}}")
        for i,(_,r) in enumerate(rows):
            for j,c in enumerate(cols):
                val=r[c]
                if c in ("valor_estoque","valor_vendido"): txt=brl(val)
                elif c=="giro": txt=f"{val:.1f}%"
                elif isinstance(val,float): txt=br_number(val,0)
                else: txt=str(val)
                item=QTableWidgetItem(txt)
                if i%2==0: item.setBackground(QColor("#FFFFFF"))
                else: item.setBackground(QColor("#F7FAFF"))
                t.setItem(i,j,item)
                if critical_mode and c=="status_estoque":
                    status=str(val).upper(); item.setText(f"  {status}  ")
                    colors={"CRÍTICO":("#FFF0F2","#D9284B"),"BAIXO":("#FFF5D9","#B77900"),"SEM ESTOQUE":("#FFE4E8","#B91C3A"),"NEGATIVO":("#7F1D1D","#FFFFFF"),"NORMAL":("#E8FAF5","#087F6A"),"EXCESSO":("#EEF2FF","#4C5BD4")}
                    bg,fg=colors.get(status,("#F1F4F8","#5F6D82")); item.setBackground(QColor(bg)); item.setForeground(QColor(fg)); item.setFont(QFont("Segoe UI",9,QFont.Weight.Bold))
        t.cellDoubleClicked.connect(lambda rr,cc,rs=rows:self.open_row(rs,rr)); self.body.addWidget(t)
    def open_row(self,rows,r):
        if 0<=r<len(rows): self.open_row_dict(rows[r][1].to_dict())
    def open_row_dict(self,row): ProductModal(row,self).exec()
    def detail(self,name,d):
        if name=="Unidades em estoque":
            self.show_store_stock(d); return
        # KPIs financeiros/quantitativos abrem o mesmo conjunto de dados que compõe o número.
        sem_vendas = d[d.produto_sem_venda].sort_values(
            ["valor_estoque", "quantidade_estoque"], ascending=[False, False], kind="stable"
        )
        criticos_kpi = d[d.status_estoque == "CRÍTICO"].sort_values(
            ["risco_ruptura", "cobertura", "quantidade_vendida", "valor_vendido"],
            ascending=[False, True, False, False],
            kind="stable",
        )
        # Com o status SEM ESTOQUE ou NEGATIVO, o valor em estoque lista esses
        # produtos (os mais negativos primeiro) em vez de só estoque positivo.
        zero_or_negative = self.status.currentText() in ("SEM ESTOQUE", "NEGATIVO")
        stock_value = (
            d.sort_values(["quantidade_estoque", "valor_estoque"], ascending=[True, True], kind="stable")
            if zero_or_negative else
            d[d.quantidade_estoque>0].sort_values(
                ["valor_estoque", "quantidade_estoque"], ascending=[False, False], kind="stable"
            )
        )
        if zero_or_negative and name == "Valor em estoque":
            name = f"Valor em estoque • {'Negativos' if self.status.currentText() == 'NEGATIVO' else 'Sem estoque'}"
        mapping={
            name if zero_or_negative else "Valor em estoque": stock_value,
            "Unidades vendidas": d[d.quantidade_vendida>0].sort_values(
                ["quantidade_vendida", "valor_vendido"], ascending=[False, False], kind="stable"
            ),
            "Produtos sem vendas": sem_vendas,
            "Produtos em ruptura": rupture(d),
            "Críticos": criticos_kpi,
            "Produtos críticos": criticos_kpi,
            "Em ruptura": rupture(d),
            "Sem vendas": sem_vendas,
        }
        if name in mapping:self.show_product_list(name,mapping[name])
    def show_store_stock(self,d):
        """Quantas unidades de cada produto cada loja tem (uma coluna por loja)."""
        table,stores,totals=stock_by_store(d)
        dlg=QDialog(self); dlg.setWindowTitle("Estoque por loja"); dlg.resize(1180,700)
        dlg.setStyleSheet("QDialog{background:#F4F7FC;} QLabel{background:transparent;}")
        l=QVBoxLayout(dlg); l.setContentsMargins(12,8,12,12); l.setSpacing(10); install_mac_window_chrome(dlg,l)
        filters=[x for x in (self.group.currentText(),self.sub.currentText()) if x not in ("Todos os grupos","Todas as subclasses")]
        head=QLabel(f"📦  Estoque por loja{' • ' + ' › '.join(filters) if filters else ''} • {br_number(len(table),0)} produtos")
        head.setStyleSheet("font-size:18px;font-weight:900;color:#12213D;padding:4px;"); l.addWidget(head)
        chips=QHBoxLayout(); chips.setSpacing(8)
        for store in stores:
            value=totals[store]
            chip=QLabel(f"🏬  {store}   {br_number(value,0)} un.")
            chip.setStyleSheet("background:#FFFFFF;border:1px solid #DCE6F3;border-radius:12px;padding:7px 12px;"
                               f"color:{'#B91C3A' if value<0 else '#17326F'};font-size:12px;font-weight:900;")
            chips.addWidget(chip)
        chips.addStretch(); l.addLayout(chips)
        hint=QLabel("Clique na quantidade de uma loja para abrir o card do produto naquela loja.  "
                    "“—” = o produto não está na planilha de estoque da loja.")
        hint.setStyleSheet("color:#7A879D;font-size:11px;padding:0 4px;"); l.addWidget(hint)
        headers=["Produto","Código","Subclasse",*stores,"Total"]
        t=QTableWidget(len(table)+(1 if len(table) else 0),len(headers)); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False); t.setAlternatingRowColors(True)
        bold=QFont("Segoe UI",9,QFont.Weight.Bold)
        def qty_item(value):
            if value!=value:  # NaN: produto ausente na planilha da loja
                item=QTableWidgetItem("—"); item.setForeground(QColor("#A3AEC0"))
            else:
                item=QTableWidgetItem(br_number(value,0)); item.setFont(bold)
                if value<0: item.setForeground(QColor("#B91C3A")); item.setBackground(QColor("#FFF0F2"))
                elif value==0: item.setForeground(QColor("#B77900")); item.setBackground(QColor("#FFF8E6"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); return item
        for i,row in table.iterrows():
            for j,v in enumerate((row.descricao,row.codigo_barras,row.subclasse)): t.setItem(i,j,QTableWidgetItem(str(v)))
            for k,store in enumerate(stores): t.setItem(i,3+k,qty_item(row[store]))
            total=qty_item(row.total); total.setBackground(QColor("#EEF3FF")); t.setItem(i,len(headers)-1,total)
        if len(table):
            last=len(table); label=QTableWidgetItem("TOTAL POR LOJA"); label.setFont(bold); t.setItem(last,0,label)
            for k,store in enumerate(stores): t.setItem(last,3+k,qty_item(totals[store]))
            grand=qty_item(sum(totals.values())); grand.setBackground(QColor("#DCE6FF")); t.setItem(last,len(headers)-1,grand)
            for j in range(len(headers)):
                if t.item(last,j): t.item(last,j).setBackground(QColor("#DCE6FF"))
        header=t.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeToContents); header.setSectionResizeMode(0,QHeaderView.Stretch)
        def open_cell(r,c):
            if r>=len(table) or not (3<=c<3+len(stores)): return
            store=stores[c-3]; code=table.iloc[r].codigo_barras
            rows=d[(d.codigo_barras==code)&(d.loja==store)]
            if len(rows): self.open_row_dict(rows.iloc[0].to_dict())
        t.cellClicked.connect(open_cell); l.addWidget(t,1); dlg.exec()
    def show_product_list(self,title,d):
        dlg=QDialog(self); dlg.setWindowTitle(title); dlg.resize(1180,700); l=QVBoxLayout(dlg); l.setContentsMargins(12,8,12,12); install_mac_window_chrome(dlg,l)
        head=QLabel(f"{title} • {br_number(len(d),0)} registros")
        head.setStyleSheet("font-size:18px;font-weight:900;color:#12213D;padding:4px;"); l.addWidget(head)
        hint=QLabel("Clique em um produto para abrir o card com todos os detalhes." if len(d) else "Nenhum produto com os filtros atuais.")
        hint.setStyleSheet("color:#7A879D;font-size:11px;padding:0 4px 4px 4px;"); l.addWidget(hint)
        headers=["Código","Produto","Grupo","Subclasse","Loja","Estoque","Vendas","Preço venda","Faturamento","Valor estoque","Status"]
        status_colors={"NEGATIVO":("#7F1D1D","#FFFFFF"),"SEM ESTOQUE":("#FFE4E8","#B91C3A"),"CRÍTICO":("#FFF0F2","#D9284B"),"BAIXO":("#FFF5D9","#B77900"),"NORMAL":("#E8FAF5","#087F6A"),"EXCESSO":("#EEF2FF","#4C5BD4")}
        t=QTableWidget(len(d),len(headers)); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setHorizontalHeaderLabels(headers); t.setSortingEnabled(False)
        t.setSelectionBehavior(QTableWidget.SelectRows); t.verticalHeader().setVisible(False); t.setCursor(Qt.CursorShape.PointingHandCursor); rows=list(d.iterrows())
        for i,(_,r) in enumerate(rows):
            vals=[r.codigo_barras,r.descricao,r.grupo,r.subclasse,r.loja,r.quantidade_estoque,r.quantidade_vendida,r.preco_venda,r.valor_vendido,r.valor_estoque,r.status_estoque]
            for j,v in enumerate(vals):
                if j in (7,8,9): txt=brl(v)
                elif isinstance(v,(float,int)): txt=br_number(v,0)
                else: txt=str(v)
                item=QTableWidgetItem(txt)
                if j==5 and r.quantidade_estoque<0: item.setForeground(QColor("#B91C3A")); item.setFont(QFont("Segoe UI",9,QFont.Weight.Bold))
                if j==10:
                    bg,fg=status_colors.get(str(v).upper(),("#F1F4F8","#5F6D82")); item.setBackground(QColor(bg)); item.setForeground(QColor(fg)); item.setFont(QFont("Segoe UI",9,QFont.Weight.Bold))
                t.setItem(i,j,item)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); t.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); t.setAlternatingRowColors(True)
        t.cellClicked.connect(lambda rr,cc:self.open_row_dict(rows[rr][1].to_dict())); l.addWidget(t); dlg.exec()
    def export_pdf(self):
        p=get_save_file(self,"Exportar PDF","MixModaInsights.pdf","PDF (*.pdf)","pdf")
        if not p: return
        try:
            export_dashboard_pdf(p,self.current_df(),self.period,self.store.currentText(),self.audit)
        except PermissionError:
            show_message(self, "critical", "Não foi possível salvar o PDF",
                         "O arquivo está aberto em outro programa (ex.: leitor de PDF). Feche-o ou escolha outro nome e tente de novo.")
            return
        except Exception as error:
            show_message(self, "critical", "Não foi possível gerar o PDF", f"{type(error).__name__}: {error}")
            return
        show_message(self, "information", "PDF","Dashboard exportado com sucesso.")

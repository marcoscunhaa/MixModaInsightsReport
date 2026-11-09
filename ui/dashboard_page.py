from utils.formatting import brl, br_number
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QLineEdit,QLabel,QTableWidget,
    QTableWidgetItem,QScrollArea,QGridLayout,QFrame,QPushButton,QHeaderView,QDialog,
    QListWidget,QListWidgetItem,QAbstractItemView)
from PySide6.QtGui import QColor, QFont
from ui.widgets import Card, KpiCard, RankCard, StatusFilterBar
from ui.explorer_cards import ExplorerCard, SUBCLASS_COLORS, _stable_color
from core.kpi_view import STATUS_OPTIONS, kpi_cards, status_counts, store_list_view
from ui.product_modal import ProductModal
from ui.product_picker import ProductPickerDialog
from charts.dashboard_charts import make_chart
from core.analyzer import filter_analysis,kpis,single_product_labels,pivot_by_store,top_sold,stagnant,critical,rupture,sort_products
from core.stores import order_stores
from ui.copyable import is_barcode_column, make_barcode_copyable
from core.insights import generate_insights
from utils.normalization import normalize_barcode, normalize_text
from exports.pdf_export import export_dashboard_pdf
from ui.stock_alerts import StockAlertsDialog
from ui.window_chrome import get_save_file, install_mac_window_chrome, show_message
from core.unclassified import is_unclassified, merge_by_barcode, product_count, unclassified_rows
from ui.unclassified_dialog import UnclassifiedDialog, export_unclassified_excel
from ui.inventory_excel import export_inventory_excel
from ui.ui_kit import BRAND_GRADIENT_DIAGONAL, brand_bar, brand_eyebrow, button, section_header

# Títulos de coluna em português claro (as tabelas usam os nomes internos das colunas).
COLUMN_LABELS = {
    "codigo_barras":"Código","descricao":"Produto","grupo":"Grupo","subclasse":"Subclasse","loja":"Loja",
    "quantidade_vendida":"Vendidas","valor_vendido":"Faturamento","giro":"Giro","quantidade_estoque":"Em estoque",
    "valor_estoque":"Valor em estoque","status_estoque":"Status",
}
CLICK_HINT="Clique num produto para ver todos os detalhes  •  Dois cliques no código para copiar."

SUBCLASS_EMOJIS = ["👗","👚","👕","👖","👟","🥿","👜","💄","💍","🧸","🏠","🛏️","🍳","🧴","🧢","🩱","🩴","🎀","🧦","🧺"]

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


class _AutoHeightCardGrid(QListWidget):
    """Grade de cards que cresce até mostrar todos os cards (a rolagem fica com o dashboard)."""

    GRID=QSize(350,116)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("CardGrid"); self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setMovement(QListWidget.Movement.Static); self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust); self.setSpacing(10); self.setGridSize(self.GRID)
        self.setUniformItemSizes(False); self.setWrapping(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def fit_height(self):
        columns=max(1,self.viewport().width()//self.GRID.width())
        rows=max(1,-(-self.count()//columns))
        self.setFixedHeight(rows*self.GRID.height()+2*self.frameWidth()+12)

    def resizeEvent(self,event):
        super().resizeEvent(event); self.fit_height()


class HierarchyBrowser(QFrame):
    """Cards navegáveis Grupo › Subclasse › Produto.

    `inline=True` é o modo do dashboard: fica dentro da página, cresce até mostrar
    todos os cards e "← Voltar" só aparece depois de entrar num grupo. No modo
    janela (explorador em diálogo) a lista rola sozinha.
    """

    def __init__(self, df, catalog=None, start_group=None, inline=False, parent=None, on_path=None):
        super().__init__(parent); self.setObjectName("PanelBody")
        self.df=df.copy(); self.path=[]; self.catalog=catalog; self.inline=inline; self.on_path=on_path
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        head=QHBoxLayout(); head.setSpacing(12)
        self.back=button("← Voltar","Ghost","Voltar um nível"); self.back.clicked.connect(self.go_back); head.addWidget(self.back,0,Qt.AlignmentFlag.AlignVCenter)
        titlebox=QVBoxLayout(); titlebox.setSpacing(2); self.title=QLabel("Explorador de catálogo"); self.title.setObjectName("SectionTitle" if inline else "PageTitle"); titlebox.addWidget(self.title)
        self.crumb=QLabel(""); self.crumb.setObjectName("Crumb"); titlebox.addWidget(self.crumb); head.addLayout(titlebox); head.addStretch()
        self.excel=QPushButton("⬇  Excel para cadastro"); self.excel.setObjectName("AddStore"); self.excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.excel.setToolTip("Baixa os produtos sem classificação, uma aba por loja, com sugestão de grupo e subclasse."); self.excel.clicked.connect(lambda: export_unclassified_excel(self,self.df,self.catalog)); head.addWidget(self.excel)
        root.addLayout(head)
        self.tip=QLabel(); self.tip.setObjectName("SectionHint"); root.addWidget(self.tip)
        if inline:
            self.list=_AutoHeightCardGrid()
        else:
            self.list=QListWidget(); self.list.setObjectName("CardGrid"); self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection); self.list.setMovement(QListWidget.Movement.Static); self.list.setViewMode(QListWidget.ViewMode.IconMode); self.list.setResizeMode(QListWidget.ResizeMode.Adjust); self.list.setSpacing(10); self.list.setGridSize(QSize(350,116)); self.list.setUniformItemSizes(False)
        self.list.itemClicked.connect(self.open_item); root.addWidget(self.list,0 if inline else 1)
        self.empty=QLabel("Nenhum produto com os filtros atuais."); self.empty.setObjectName("Muted"); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty.setStyleSheet("padding:24px;"); self.empty.hide(); root.addWidget(self.empty)
        self.render_group(start_group) if start_group else self.render_groups()

    # ---------- montagem ----------
    def _show_excel(self,group=None):
        # Só faz sentido onde há produto sem classificação.
        self.excel.setVisible(group is not None and is_unclassified(group) and not unclassified_rows(self.df).empty)

    def _begin(self,path,title,crumb,tip):
        self.path=path; self.title.setText(title); self.crumb.setText(crumb); self.tip.setText(tip); self.list.clear()
        if self.inline: self.back.setVisible(bool(path))
        else: self.back.setEnabled(bool(path))
        if self.on_path: self.on_path(list(path))

    def _finish(self):
        self.empty.setVisible(self.list.count()==0); self.list.setVisible(self.list.count()>0)
        if self.inline: self.list.fit_height()

    @staticmethod
    def _counts(d,key):
        """Produtos por `key`; os sem classificação contam uma vez por código (não uma por loja)."""
        return {k:product_count(part) for k,part in d.groupby(key,dropna=False)}

    def _add_card(self,title,subtitle,value,key,kind,accent,emoji,tooltip=""):
        item=QListWidgetItem(); item.setData(Qt.ItemDataRole.UserRole,(kind,key)); item.setSizeHint(QSize(340,104)); self.list.addItem(item)
        card=ExplorerCard(emoji,title,subtitle,value,accent,flat=True,copyable_subtitle=(kind=="product"))
        if tooltip: card.setToolTip(tooltip)
        self.list.setItemWidget(item,card)

    @staticmethod
    def _summary(d,key):
        out=d.groupby(key,dropna=False).agg(produtos=("codigo_barras","count"),vendas=("quantidade_vendida","sum"),estoque=("quantidade_estoque","sum"),
                                            valor_estoque=("valor_estoque","sum"),faturamento=("valor_vendido","sum"),giro=("giro","mean")).reset_index()
        return out

    @staticmethod
    def _tip(r):
        return (f"Estoque: {br_number(r.estoque,0)} un.  •  Valor em estoque: {brl(r.valor_estoque)}\n"
                f"Vendas: {br_number(r.vendas,0)} un.  •  Faturamento: {brl(r.faturamento)}\n"
                f"Giro médio: {br_number(r.giro,1)}%\n\nClique para abrir")

    def render_groups(self):
        self._begin([],"Explorar por grupo" if self.inline else "Explorador • Grupos","Todos os grupos",
                    "Clique num grupo para ver as subclasses e, depois, os produtos.")
        g=self._summary(self.df,"grupo"); counts=self._counts(self.df,"grupo"); g["produtos"]=g["grupo"].map(counts).fillna(g["produtos"]); self._show_excel()
        g["_ord"]=g["grupo"].map(lambda x: normalize_text(x)); g=g.sort_values("_ord",kind="stable")
        for _,r in g.iterrows():
            name=str(r.grupo)
            self._add_card(name,f"{br_number(r.produtos,0)} produtos  •  {br_number(r.estoque,0)} em estoque",
                           f"{br_number(r.vendas,0)} vendas  •  {brl(r.faturamento,0)}",name,"group",_stable_color(name),"",self._tip(r))
        self._finish()

    def render_group(self,g):
        self._begin([("group",g)],f"{g} • Subclasses",f"Todos os grupos  ›  {g}","Clique numa subclasse para ver os produtos.")
        d=self.df[self.df.grupo==g]; x=self._summary(d,"subclasse")
        counts=self._counts(d,"subclasse"); x["produtos"]=x["subclasse"].map(counts).fillna(x["produtos"]); self._show_excel(g)
        x["_nome"]=x["subclasse"].map(lambda v: "Sem subclasse" if str(v)=="nan" else str(v))
        x["_ord"]=x["_nome"].map(normalize_text); x=x.sort_values("_ord",kind="stable")
        for _,r in x.iterrows():
            sub=r["_nome"]
            self._add_card(sub,f"{br_number(r.produtos,0)} produtos  •  {br_number(r.estoque,0)} em estoque",
                           f"{br_number(r.vendas,0)} vendas  •  {brl(r.faturamento,0)}",sub,"sub",_stable_color(sub),"",self._tip(r))
        self._finish()

    def render_sub(self,g,sub):
        self._begin([("group",g),("sub",sub)],f"Produtos • {sub}",f"Todos os grupos  ›  {g}  ›  {sub}",
                    "Clique num produto para ver todos os detalhes  •  Dois cliques no código para copiar.")
        d=self.df[(self.df.grupo==g)&(self.df.subclasse==sub)].copy()
        self._show_excel(g)
        if is_unclassified(g) or is_unclassified(sub):
            # Sem classificação: um card por código, com as lojas onde ele está.
            for r in merge_by_barcode(d):
                n=len(r["lojas"]); where=r["loja"] if n<=2 else f"{n} lojas"
                self._add_card(str(r["descricao"]),f"{r['codigo_barras']}  •  {where}",f"{br_number(r['quantidade_estoque'],0)} em estoque  •  {br_number(r['quantidade_vendida'],0)} vendas",r,"product",_stable_color(str(r["descricao"])),"")
            self._finish(); return
        d=sort_products(d)  # código de barras do menor para o maior (P → GG) e lojas na ordem oficial
        for _,r in d.iterrows():
            accent=_stable_color(str(r.descricao)); self._add_card(str(r.descricao),f"{r.codigo_barras}  •  {r.loja}",f"{br_number(r.quantidade_vendida,0)} vendas  •  {brl(r.valor_vendido)}",r.to_dict(),"product",accent,"")
        self._finish()

    def restore(self,path):
        """Volta ao nível em que o usuário estava, se ele ainda existir com os filtros atuais."""
        groups=set(self.df.grupo.dropna().astype(str))
        if path and str(path[0][1]) in groups:
            g=path[0][1]
            if len(path)==2 and ((self.df.grupo==g)&(self.df.subclasse==path[1][1])).any(): self.render_sub(g,path[1][1])
            else: self.render_group(g)

    # ---------- navegação ----------
    def open_item(self,item):
        kind,key=item.data(Qt.ItemDataRole.UserRole)
        if kind=="group": self.render_group(key)
        elif kind=="sub": self.render_sub(self.path[0][1],key)
        elif kind=="product": ProductModal(key,self).exec()

    def go_back(self):
        if len(self.path)==2: self.render_group(self.path[0][1])
        elif len(self.path)==1: self.render_groups()


class HierarchyExplorer(QDialog):
    """O mesmo explorador numa janela própria."""

    def __init__(self, df, start_group=None, parent=None, catalog=None):
        super().__init__(parent)
        self.setWindowTitle("Explorador de Produtos • Mix Moda Insights"); self.resize(1180,720)
        root=QVBoxLayout(self); root.setContentsMargins(12,8,12,12); root.setSpacing(12); install_mac_window_chrome(self,root)
        self.browser=HierarchyBrowser(df,catalog,start_group,inline=False,parent=self); root.addWidget(self.browser,1)
        self.list=self.browser.list


class DashboardPage(QWidget):
    def __init__(self,df,period,audit,parent=None,on_home=None,alert_store=None,catalog=None):
        super().__init__(parent); self.df=df; self.period=period; self.audit=audit; self.alert_store=alert_store; self.catalog=catalog
        root=QVBoxLayout(self); root.setContentsMargins(28,18,28,22); root.setSpacing(12)
        # Cabeçalho em cartão com as cores da Mix Moda: voltar à esquerda, qual análise é esta
        # (período e lojas) no meio, avisos e a ação principal à direita.
        hero=QFrame(); hero.setObjectName("DashHero")
        hero.setStyleSheet(
            "QFrame#DashHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FFF8E7,stop:0.38 #FFFFFF,stop:1 #FFFFFF);"
            "border:1px solid #EFE2C4;border-radius:20px;}"
            "QFrame#DashHero QLabel{background:transparent;border:none;}"
            f"QFrame#DashHero QLabel#HeroIcon{{background:{BRAND_GRADIENT_DIAGONAL};border-radius:16px;font-size:24px;}}"
            "QFrame#DashHero QLabel#HeroTitle{color:#12213D;font-size:24px;font-weight:900;}"
            "QFrame#DashHero QLabel#HeroStore{background:#FFFFFF;border:1px solid #EFE2C4;border-radius:11px;"
            "padding:4px 11px;color:#5A4A2A;font-size:11px;font-weight:800;}"
        )
        head=QHBoxLayout(hero); head.setContentsMargins(18,16,18,16); head.setSpacing(14)
        if on_home:
            home_button=button("← Início","Ghost","Voltar para a tela inicial",on_home); head.addWidget(home_button,0,Qt.AlignmentFlag.AlignVCenter)
        icon=QLabel("📊"); icon.setObjectName("HeroIcon"); icon.setFixedSize(56,56); icon.setAlignment(Qt.AlignmentFlag.AlignCenter); head.addWidget(icon,0,Qt.AlignmentFlag.AlignVCenter)
        brand=QVBoxLayout(); brand.setSpacing(5)
        brand.addWidget(brand_eyebrow("INSIGHTS  •  DASHBOARD"))
        title=QLabel(self._period_title()); title.setObjectName("HeroTitle"); brand.addWidget(title)
        brand.addWidget(brand_bar(88,4))
        stores=order_stores(df.loja.dropna().unique()) if "loja" in df else []
        chips=QHBoxLayout(); chips.setSpacing(6)
        for store in stores:
            chip=QLabel(f"🏬  {store}"); chip.setObjectName("HeroStore"); chips.addWidget(chip)
        if not len(stores):
            chip=QLabel("Estoque, vendas, faturamento e giro por loja"); chip.setObjectName("Subtitle"); chips.addWidget(chip)
        chips.addStretch(); brand.addLayout(chips)
        head.addLayout(brand,1)
        self.alert_button=QPushButton()
        self.alert_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.alert_button.clicked.connect(self.open_stock_alerts)
        head.addWidget(self.alert_button,0,Qt.AlignmentFlag.AlignVCenter)
        self.unclassified_button=QPushButton(); self.unclassified_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unclassified_button.setStyleSheet("QPushButton{background:#FFF7E0;color:#A35A00;border:1px solid #F3D28B;border-radius:12px;padding:10px 15px;font-weight:900;}"
                                               "QPushButton:hover{background:#FFEFC2;border-color:#E8B24A;}")
        self.unclassified_button.setToolTip("Produtos sem grupo ou subclasse no catálogo.\nAbre a lista (um por código) e gera o Excel para cadastro.")
        self.unclassified_button.clicked.connect(lambda: UnclassifiedDialog(self.current_df(),self.catalog,self).exec()); head.addWidget(self.unclassified_button,0,Qt.AlignmentFlag.AlignVCenter)
        self.inventory_button=button("📦  Excel do estoque","Secondary",
            "Baixa o estoque completo (todas as lojas, sem os filtros da tela):\n"
            "resumo, visão Grupo › Subclasse › Produto que abre e fecha, aba geral e uma aba por loja,\n"
            "com busca e filtros por código, nome, loja, grupo e subclasse.",self.export_inventory)
        head.addWidget(self.inventory_button,0,Qt.AlignmentFlag.AlignVCenter)
        pdf=button("📄  Exportar PDF","Primary","Gera um relatório em PDF com o que está filtrado na tela.",self.export_pdf); head.addWidget(pdf,0,Qt.AlignmentFlag.AlignVCenter); root.addWidget(hero)
        filters=QFrame(); filters.setObjectName("Panel"); fbox=QVBoxLayout(filters); fbox.setContentsMargins(16,12,16,12); fbox.setSpacing(10)
        ftop=QHBoxLayout(); ftop.setSpacing(8); fcap=QLabel("🔎  FILTROS"); fcap.setObjectName("FieldLabel"); ftop.addWidget(fcap)
        fhint=QLabel("Tudo abaixo — números, gráficos e tabelas — segue o que você escolher aqui."); fhint.setObjectName("SectionHint"); ftop.addWidget(fhint,1)
        self.clear_filters_button=button("↺  Limpar filtros","Link","Volta a mostrar todas as lojas, grupos, status e produtos.",self.clear_filters); ftop.addWidget(self.clear_filters_button); fbox.addLayout(ftop)
        fl=QHBoxLayout(); fl.setSpacing(8); fbox.addLayout(fl)
        self.store=QComboBox(); self.store.addItem("Todas as lojas"); self.store.addItems(order_stores(df.loja.dropna().unique())); self.group=QComboBox(); self.group.addItem("Todos os grupos"); self.group.addItems(sorted(df.grupo.dropna().unique())); self.sub=QComboBox(); self.sub.addItem("Todas as subclasses"); self.status=StatusFilterBar(STATUS_OPTIONS); self.search=QLineEdit(); self.search.setPlaceholderText("🔍  Buscar produto, código, grupo ou subclasse..."); self.search.setClearButtonEnabled(True)
        self.store.setToolTip("Escolha uma loja ou veja todas juntas"); self.group.setToolTip("Escolha um grupo de produtos"); self.sub.setToolTip("Escolha uma subclasse do grupo")
        self.selected_codes=set()  # produtos marcados em "Selecionar produtos"; vazio = todos
        self.pick=QPushButton(); self.pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pick.setToolTip("Marque vários produtos (ex.: os tamanhos de um conjunto); o dashboard inteiro passa a mostrar só eles."); self.pick.clicked.connect(self.open_product_picker)
        for w in (self.store,self.group,self.sub,self.search,self.pick): fl.addWidget(w)
        fl.setStretch(3,1); fbox.addWidget(self._selection_bar()); fbox.addWidget(self.status)
        root.addWidget(filters)
        sc=QScrollArea(); sc.setWidgetResizable(True); inner=QWidget(); self.body=QVBoxLayout(inner); self.body.setContentsMargins(0,0,6,0); self.body.setSpacing(14); sc.setWidget(inner); root.addWidget(sc,1)
        self.store.currentTextChanged.connect(self.refresh); self.group.currentTextChanged.connect(self.refresh); self.sub.currentTextChanged.connect(self.refresh); self.status.currentTextChanged.connect(self.refresh); self.search.textChanged.connect(self.refresh); self._update_selection_ui(); self.refresh()

    def _period_title(self):
        from core.last_analysis import _iso, describe_period
        try:
            start,end=self.period
        except (TypeError,ValueError):
            return "Análise"
        return f"Análise de {describe_period({'data_inicio':_iso(start),'data_fim':_iso(end)})}"

    def _filters_active(self):
        return bool(self.store.currentIndex()>0 or self.group.currentIndex()>0 or self.sub.currentIndex()>0
                    or self.search.text().strip() or self.status.currentText()!=STATUS_OPTIONS[0][0] or self.selected_codes)

    def clear_filters(self):
        """Volta ao dashboard completo: todas as lojas, grupos, subclasses, status e produtos."""
        widgets=(self.store,self.group,self.sub,self.search,self.status)
        for w in widgets: w.blockSignals(True)
        self.store.setCurrentIndex(0); self.group.setCurrentIndex(0); self.sub.setCurrentIndex(0); self.search.clear()
        self.status.setCurrentText(STATUS_OPTIONS[0][0])
        for w in widgets: w.blockSignals(False)
        self.selected_codes=set(); self._update_selection_ui(); self.refresh()

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
        self.alert_button.setText(f"🔔  {br_number(count,0)} alerta{'s' if count!=1 else ''}" if count else "🔔  Sem alertas")
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
            f"{count} produto(s) atingiram as regras de estoque mínimo.\nClique para ver a lista e exportar para Excel."
            if count else "Nenhum produto atingiu as regras de estoque mínimo.\nAs regras são criadas em Alertas de estoque, na tela inicial."
        )

    def apply_catalog(self,catalog):
        """O catálogo mudou: reaplica grupo/subclasse e redesenha (filtros e seleção ficam)."""
        from core.matcher import reclassify
        self.catalog=catalog; self.df,changed=reclassify(self.df,catalog)
        if changed: self.refresh()

    def refresh_unclassified_button(self,d):
        n=len(merge_by_barcode(unclassified_rows(d)))
        self.unclassified_button.setText(f"📋  {br_number(n,0)} sem classificação"); self.unclassified_button.setVisible(bool(n))

    def open_stock_alerts(self):
        StockAlertsDialog(self._filtered_alerts(), self).exec()

    def _selection_bar(self):
        """Faixa que aparece com a seleção ativa: quantos produtos, quais, Editar e Limpar."""
        bar=QFrame(); bar.setObjectName("SelectionBar")
        bar.setStyleSheet("QFrame#SelectionBar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #EEF3FF,stop:1 #F6F2FF);"
                          "border:1px solid #C9D6FF;border-radius:14px;} QFrame#SelectionBar QLabel{background:transparent;border:none;}"
                          # Com o prefixo QFrame#SelectionBar para vencer a regra "QLabel transparente" acima.
                          "QFrame#SelectionBar QLabel#selBadge{background:#2F5BEA;color:#FFFFFF;border-radius:11px;padding:5px 12px;font-size:11px;font-weight:900;}"
                          "QFrame#SelectionBar QLabel#selNames{color:#33456A;font-size:11px;font-weight:700;}"
                          "QPushButton#selEdit{background:#FFFFFF;color:#2F5BEA;border:1px solid #C9D6FF;border-radius:10px;padding:6px 12px;font-weight:900;}"
                          "QPushButton#selEdit:hover{background:#EEF3FF;}"
                          "QPushButton#selClear{background:transparent;color:#7A879D;border:none;padding:6px 8px;font-weight:900;}"
                          "QPushButton#selClear:hover{color:#D9284B;}")
        row=QHBoxLayout(bar); row.setContentsMargins(12,8,8,8); row.setSpacing(10)
        self.sel_badge=QLabel(); self.sel_badge.setObjectName("selBadge"); row.addWidget(self.sel_badge)
        self.sel_names=QLabel(); self.sel_names.setObjectName("selNames"); row.addWidget(self.sel_names,1)
        edit=QPushButton("Editar seleção"); edit.setObjectName("selEdit"); edit.setCursor(Qt.CursorShape.PointingHandCursor); edit.clicked.connect(self.open_product_picker); row.addWidget(edit)
        clear=QPushButton("✕  Limpar"); clear.setObjectName("selClear"); clear.setCursor(Qt.CursorShape.PointingHandCursor); clear.setToolTip("Voltar a analisar todos os produtos")
        clear.clicked.connect(lambda checked=False:self.set_selection(set())); row.addWidget(clear)
        self.selection_bar=bar; return bar
    def _update_selection_ui(self):
        n=len(self.selected_codes)
        self.pick.setText(f"☑  {br_number(n,0)} selecionado{'s' if n!=1 else ''}" if n else "☑  Selecionar produtos")
        self.pick.setObjectName("" if n else "Secondary"); self.pick.style().unpolish(self.pick); self.pick.style().polish(self.pick)
        self.selection_bar.setVisible(bool(n))
        if n:
            names=(self.df[self.df.codigo_barras.isin(self.selected_codes)].drop_duplicates("codigo_barras")
                   .pipe(sort_products).descricao.astype(str).tolist())
            shown=", ".join(names[:4])+(f"  e mais {br_number(len(names)-4,0)}" if len(names)>4 else "")
            self.sel_badge.setText(f"🎯  {br_number(n,0)} produto{'s' if n!=1 else ''} na análise"); self.sel_names.setText(shown); self.sel_names.setToolTip("\n".join(names))
    def set_selection(self,codes):
        self.selected_codes=set(codes); self._update_selection_ui(); self.refresh()
    def _apply_selection(self,d):
        return d[d.codigo_barras.isin(self.selected_codes)] if self.selected_codes else d
    def current_df(self):
        status="Todos" if self.status.currentText()=="Todos os status" else self.status.currentText(); return self._apply_selection(filter_analysis(self.df,*self._base_filters(),status))
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
        options=self._apply_selection(self.df)
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
        self.status.set_counts(status_counts(self._apply_selection(filter_analysis(self.df,*self._base_filters(),"Todos"))))
        self.clear_filters_button.setVisible(self._filters_active())
        d=self.current_df(); self.refresh_alert_button(); self.refresh_unclassified_button(d); self.clear_body()
        self.body.addWidget(section_header("RESUMO","Os cards com “Ver lista ›” abrem os produtos por loja. Passe o mouse num card para mais detalhes."))
        grid=QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(12)
        for i,spec in enumerate(kpi_cards(d)):
            c=KpiCard(spec["label"],spec["value"],spec["hint"],spec["accent"],spec["emoji"],spec["tone"],spec["clickable"])
            if spec["clickable"]: c.clicked.connect(lambda name=spec["key"]:self.detail(name,d))
            grid.addWidget(c,i//5,i%5)
        self.body.addLayout(grid)
        row1=QHBoxLayout(); row1.setSpacing(12); row1.addWidget(self.panel("🏆  TOP 3 MAIS VENDIDOS",self.top3(d),"Clique num produto para ver os detalhes."),1); row1.addWidget(self.panel("🏬  RANKING POR LOJA",self.store_ranking(d),"Lojas ordenadas pelas unidades vendidas no período."),1); self.body.addLayout(row1)
        self.body.addWidget(section_header("GRÁFICOS","Visão geral do estoque e das vendas por grupo."))
        charts=QGridLayout(); charts.setSpacing(12)
        for i,k in enumerate(["grupo_valor_3d","grupo_pizza","vendas_3d","rotacao","status","estoque_x_vendas"]): charts.addWidget(self.chart_panel(make_chart(k,d)),i//2,i%2)
        self.body.addLayout(charts)
        self.body.addWidget(self.group_browser(d))
        self.body.addWidget(section_header("PRODUTOS MAIS VENDIDOS",CLICK_HINT)); self.table_section(top_sold(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_vendida","valor_vendido","giro"],150,"#2F5BEA")
        self.body.addWidget(section_header("ESTOQUE PARADO  •  DINHEIRO PARADO EM PRODUTO","Produtos com estoque e pouca ou nenhuma venda. "+CLICK_HINT)); self.table_section(stagnant(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_estoque","valor_estoque"],150,"#FF9F43")
        self.body.addWidget(section_header("PRODUTOS CRÍTICOS","Produtos com estoque baixo, zerado ou negativo. "+CLICK_HINT)); self.table_section(critical(d,6),["codigo_barras","descricao","grupo","subclasse","loja","quantidade_estoque","quantidade_vendida","status_estoque"],160,"#E94B5F",critical_mode=True)
        ins=QFrame(); ins.setObjectName("Panel"); il=QVBoxLayout(ins); il.setContentsMargins(16,14,16,14); il.addWidget(self.section_label("💡  INSIGHTS DA ANÁLISE"))
        insight_colors=[("#5B6CFF","💡"),("#00A88F","📈"),("#FF9F43","⚠️"),("#E85D8A","🎯")]  # azul, verde, laranja, rosa (mesma cor do título de cada insight)
        for idx,x in enumerate(generate_insights(d)):
            accent,emoji=insight_colors[idx%len(insight_colors)]
            # Contorno propositalmente discreto: o destaque fica no conteúdo, não na borda.
            # A regra de borda é restrita ao card (#InsightCard) para não vazar para os QLabel filhos.
            r=QFrame(); r.setObjectName("InsightCard"); r.setStyleSheet(f"QFrame#InsightCard{{background:#FFFFFF;border:1px solid {_rgba(accent,0.45)};border-radius:14px;}} QLabel{{border:none;background:transparent;}} QLabel#it{{color:{accent};font-size:12px;font-weight:900;}} QLabel#ix{{color:#40516E;font-size:11px;font-weight:700;}}")
            rl=QHBoxLayout(r); rl.setContentsMargins(12,10,12,10); icon=QLabel(emoji); icon.setStyleSheet(f"font-size:21px;color:{accent};background:transparent;"); rl.addWidget(icon); box=QVBoxLayout(); a=QLabel(x['titulo']); a.setObjectName("it"); box.addWidget(a); b=QLabel(x['texto']); b.setObjectName("ix"); b.setWordWrap(True); box.addWidget(b); rl.addLayout(box,1); il.addWidget(r)
        self.body.addWidget(ins); audit=QLabel(f"Auditoria: {br_number(self.audit.get('produtos_estoque',0),0)} itens de estoque • {br_number(self.audit.get('produtos_vendas',0),0)} itens de vendas • {br_number(self.audit.get('vendas_correspondentes',0),0)} correspondências • {br_number(self.audit.get('vendas_sem_correspondencia',0),0)} vendas ignoradas"); audit.setStyleSheet("color:#7A879D;font-size:10px;font-weight:700;padding:5px;"); self.body.addWidget(audit)

    def section_label(self,text): x=QLabel(text); x.setObjectName("SectionTitle"); return x
    def panel(self,title,widget,hint=""):
        f=QFrame(); f.setObjectName("Panel"); l=QVBoxLayout(f); l.setContentsMargins(16,14,16,14); l.setSpacing(4); l.addWidget(self.section_label(title))
        if hint:
            h=QLabel(hint); h.setObjectName("SectionHint"); l.addWidget(h)
        l.addWidget(widget); return f
    def chart_panel(self,chart): f=QFrame(); f.setObjectName("Panel"); l=QVBoxLayout(f); l.setContentsMargins(8,6,8,6); l.addWidget(chart); return f
    def top3(self,d):
        w=QWidget(); w.setObjectName("PanelBody"); l=QVBoxLayout(w); l.setContentsMargins(0,6,0,0); l.setSpacing(8); rows=top_sold(d,3).reset_index(drop=True); medals=[("👑","#F3B63F"),("🥈","#6D7A91"),("🥉","#B97845")]
        for i,r in rows.iterrows(): c=RankCard(medals[i][0],r.descricao,r.quantidade_vendida,medals[i][1],r.valor_vendido); c.clicked.connect(lambda rr=r:self.open_row_dict(rr.to_dict())); l.addWidget(c)
        if rows.empty:
            e=QLabel("Nenhuma venda com os filtros atuais."); e.setObjectName("Muted"); e.setAlignment(Qt.AlignmentFlag.AlignCenter); l.addWidget(e)
        l.addStretch(); return w
    def store_ranking(self,d):
        w=QWidget(); w.setObjectName("PanelBody"); l=QVBoxLayout(w); l.setContentsMargins(0,6,0,0); l.setSpacing(8); x=d.groupby("loja",as_index=False).agg(vendas=("quantidade_vendida","sum"),faturamento=("valor_vendido","sum")).sort_values("vendas",ascending=False).head(5)
        for i,(_,r) in enumerate(x.iterrows()): c=RankCard(str(i+1),r.loja,r.vendas,["#2854D9","#16B8C8","#0F9D8A","#7C6FE6","#E85D8A"][i%5],r.faturamento); l.addWidget(c)
        l.addStretch(); return w
    def group_browser(self,d):
        """Explorar por grupo direto no dashboard, em cards (Grupo › Subclasse › Produto)."""
        f=QFrame(); f.setObjectName("Panel"); l=QVBoxLayout(f); l.setContentsMargins(16,14,16,14)
        saved=list(getattr(self,"_browser_path",[]))  # lido antes: montar a grade já avisa o caminho inicial
        browser=HierarchyBrowser(d,self.catalog,inline=True,parent=f,on_path=lambda path:setattr(self,"_browser_path",path))
        browser.restore(saved)  # filtros mudaram: continua no mesmo grupo/subclasse
        l.addWidget(browser); return f
    def table_section(self,d,cols,height=140,accent="#2F5BEA",critical_mode=False):
        t=QTableWidget(len(d),len(cols)); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setMinimumHeight(max(height, 44 + len(d)*38)); t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); t.setAlternatingRowColors(True); t.setSortingEnabled(False); t.setHorizontalHeaderLabels([COLUMN_LABELS.get(c,c.replace("_"," ").title()) for c in cols]); t.horizontalHeader().setStretchLastSection(True); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); t.verticalHeader().setVisible(False); t.setSelectionBehavior(QTableWidget.SelectRows); rows=list(d.iterrows())
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
        if "codigo_barras" in cols: make_barcode_copyable(t,cols.index("codigo_barras"))
        # Um clique abre o card (igual às listas do app); no código, dois cliques continuam copiando.
        t.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        t.cellClicked.connect(lambda rr,cc,rs=rows,tt=t:None if is_barcode_column(tt,cc) else self.open_row(rs,rr)); self.body.addWidget(t)
    def open_row(self,rows,r):
        if 0<=r<len(rows): self.open_row_dict(rows[r][1].to_dict())
    def open_row_dict(self,row,parent=None):
        # A dona do card é a janela onde o clique aconteceu; se for o dashboard
        # com uma lista aberta por cima, o card abriria atrás da lista.
        ProductModal(row,parent or self).exec()
    def detail(self,name,d):
        # Toda lista de KPI abre no formato produto × loja.
        view=store_list_view(name,d,self.status.currentText())
        if view: self.show_store_pivot(view)
    def _picker_df(self):
        """Produtos que podem ser marcados: os da loja escolhida (grupo, subclasse e status não limitam a escolha)."""
        loja="Todas" if self.store.currentText()=="Todas as lojas" else self.store.currentText()
        return filter_analysis(self.df,loja)
    def open_product_picker(self):
        """Marcar produtos: ao aplicar, o dashboard inteiro passa a considerar só eles."""
        picker=ProductPickerDialog(self._picker_df(),self.selected_codes,self.search.text() if not self.selected_codes else "",self)
        if picker.exec()==QDialog.DialogCode.Accepted:
            if picker.selected:
                self.search.blockSignals(True); self.search.clear(); self.search.blockSignals(False)  # a seleção substitui a busca
            self.set_selection(picker.selected)
    def show_store_pivot(self,view,parent=None):
        """Lista de um KPI dividida por loja: uma linha por produto, uma coluna por loja."""
        rows=view["rows"]; kind=view["kind"]
        table,stores,totals=pivot_by_store(rows,view["value"],view["ascending"])
        def fmt(value): return brl(value) if kind=="money" else br_number(value,0)
        unit="" if kind=="money" else " un."
        dlg=QDialog(parent or self); dlg.setWindowTitle(view["title"]); dlg.resize(1180,700)
        dlg.setStyleSheet("QDialog{background:#F4F7FC;} QLabel{background:transparent;}")
        l=QVBoxLayout(dlg); l.setContentsMargins(12,8,12,12); l.setSpacing(10); install_mac_window_chrome(dlg,l)
        filters=[x for x in (self.group.currentText(),self.sub.currentText()) if x not in ("Todos os grupos","Todas as subclasses")]
        head=QLabel(f"{view['emoji']}  {view['title']}{' • ' + ' › '.join(filters) if filters else ''} • {br_number(len(table),0)} produtos")
        head.setStyleSheet("font-size:18px;font-weight:900;color:#12213D;padding:4px;"); head.setWordWrap(True); l.addWidget(head)
        chips=QHBoxLayout(); chips.setSpacing(8)
        for store in stores:
            value=totals[store]
            chip=QLabel(f"🏬  {store}   {fmt(value)}{unit}")
            chip.setStyleSheet("background:#FFFFFF;border:1px solid #DCE6F3;border-radius:12px;padding:7px 12px;"
                               f"color:{'#B91C3A' if value<0 else '#17326F'};font-size:12px;font-weight:900;")
            chips.addWidget(chip)
        chips.addStretch(); l.addLayout(chips)
        absent=view.get("absent") or ("o produto não está na planilha de estoque da loja" if view["value"]=="quantidade_estoque" and len(rows)==len(self.current_df())
                else "o produto não entra nesta lista naquela loja")
        hint=QLabel(f"{view['note']}  Clique numa loja para abrir o card do produto nela.  Dois cliques no código para copiar.  “—” = {absent}."
                    if len(table) else "Nenhum produto nesta lista com os filtros atuais.")
        hint.setStyleSheet("color:#7A879D;font-size:11px;padding:0 4px;"); hint.setWordWrap(True); l.addWidget(hint)
        headers=["Produto","Código","Subclasse",*stores,"Total"]
        t=QTableWidget(len(table)+(1 if len(table) else 0),len(headers)); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False); t.setAlternatingRowColors(True)
        bold=QFont("Segoe UI",9,QFont.Weight.Bold)
        def cell(value):
            if value!=value:  # NaN: sem linha do produto nesta loja
                item=QTableWidgetItem("—"); item.setForeground(QColor("#A3AEC0"))
            else:
                item=QTableWidgetItem(fmt(value)); item.setFont(bold)
                if value<0: item.setForeground(QColor("#B91C3A")); item.setBackground(QColor("#FFF0F2"))
                elif value==0 and kind=="stock": item.setForeground(QColor("#B77900")); item.setBackground(QColor("#FFF8E6"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); return item
        for i,row in table.iterrows():
            for j,v in enumerate((row.descricao,row.codigo_barras,row.subclasse)): t.setItem(i,j,QTableWidgetItem(str(v)))
            for k,store in enumerate(stores): t.setItem(i,3+k,cell(row[store]))
            total=cell(row.total); total.setBackground(QColor("#EEF3FF")); t.setItem(i,len(headers)-1,total)
        if len(table):
            last=len(table); label=QTableWidgetItem("TOTAL POR LOJA"); label.setFont(bold); t.setItem(last,0,label)
            for k,store in enumerate(stores): t.setItem(last,3+k,cell(totals[store]))
            t.setItem(last,len(headers)-1,cell(sum(totals.values())))
            for j in range(len(headers)):
                if t.item(last,j) is None: t.setItem(last,j,QTableWidgetItem(""))
                t.item(last,j).setBackground(QColor("#DCE6FF"))
        header=t.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeToContents); header.setSectionResizeMode(0,QHeaderView.Stretch)
        def open_cell(r,c):
            if r>=len(table) or not (3<=c<3+len(stores)): return
            store=stores[c-3]; code=table.iloc[r].codigo_barras
            found=rows[(rows.codigo_barras==code)&(rows.loja==store)]
            if len(found): self.open_row_dict(found.iloc[0].to_dict(),dlg)
        make_barcode_copyable(t,1)
        t.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        t.cellClicked.connect(open_cell); l.addWidget(t,1); l.addLayout(self._close_row(dlg)); dlg.exec()
    def show_product_list(self,title,d):
        d=sort_products(d)
        dlg=QDialog(self); dlg.setWindowTitle(title); dlg.resize(1180,700); l=QVBoxLayout(dlg); l.setContentsMargins(12,8,12,12); install_mac_window_chrome(dlg,l)
        head=QLabel(f"{title} • {br_number(len(d),0)} registros")
        head.setStyleSheet("font-size:18px;font-weight:900;color:#12213D;padding:4px;"); l.addWidget(head)
        hint=QLabel("Clique em um produto para abrir o card com todos os detalhes. Dois cliques no código para copiar." if len(d) else "Nenhum produto com os filtros atuais.")
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
        make_barcode_copyable(t,0)
        t.cellClicked.connect(lambda rr,cc:None if cc==0 else self.open_row_dict(rows[rr][1].to_dict(),dlg)); l.addWidget(t); l.addLayout(self._close_row(dlg)); dlg.exec()
    @staticmethod
    def _close_row(dlg):
        row=QHBoxLayout(); row.addStretch(1); row.addWidget(button("Fechar","Ghost","Fechar esta lista",dlg.accept)); return row
    def export_inventory(self):
        # Estoque inteiro da análise: os filtros da tela não se aplicam (o Excel tem os próprios).
        return export_inventory_excel(self,self.df,self.catalog,self._period_title())
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

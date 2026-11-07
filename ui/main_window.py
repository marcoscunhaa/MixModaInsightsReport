from pathlib import Path
import traceback

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.catalog_store import classification_payload, load_catalog
from core.last_analysis import LastAnalysisError, LastAnalysisStore
from core.models import AnalysisConfig
from core.stock_alerts import StockAlertStore
from ui.analysis_page import AnalysisPage
from ui.stock_explorer import StockExplorerPage
from ui.widgets import FeatureCard, LastAnalysisCard
from core.stores import STORES
from ui.window_chrome import install_mac_window_chrome, show_message
from ui.styles import APP_QSS
from utils.formatting import br_number


class MainWindow(QMainWindow):
    def __init__(self, catalog_path, user_data_dir=None):
        super().__init__()
        self.setWindowTitle("Mix Moda Insights")
        self.resize(1580, 980)
        self.setStyleSheet(APP_QSS)

        self.catalog_path = catalog_path
        self.catalog = load_catalog(catalog_path)
        self.classification = classification_payload(self.catalog)

        data_dir = Path(user_data_dir) if user_data_dir else Path(catalog_path).resolve().parent
        self.alert_store = StockAlertStore(
            data_dir / "stock_alert_rules.json",
            data_dir / "stock_alert_snapshot.json",
        )
        self.last_analysis = LastAnalysisStore(data_dir)

        self.stack = QStackedWidget()
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self.stack)
        self.setCentralWidget(shell)
        install_mac_window_chrome(self, shell_layout)
        self.home = self.home_page()
        self.analysis = AnalysisPage(on_home=self.open_home)
        self.analysis.generate.connect(self.generate)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.analysis)
        self.stock_explorer = None
        self.dashboard = None
        self.dashboard_id = None  # id da análise salva que o dashboard atual mostra


    def home_page(self):
        widget = QWidget()
        widget.setObjectName("Shell")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(80, 64, 80, 48)
        layout.setSpacing(16)

        badge = QLabel("MIX MODA  •  INTELLIGENCE")
        badge.setStyleSheet("color:#2854D9;font-weight:900;font-size:12px;letter-spacing:2px;")
        layout.addWidget(badge)
        title = QLabel("MIX MODA INSIGHTS")
        title.setObjectName("Title")
        layout.addWidget(title)
        subtitle = QLabel("Uma central executiva para entender estoque, vendas, giro, ruptura e performance por loja.")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(14)
        # Só o resumo pequeno é lido aqui: a tela inicial continua abrindo sem pandas.
        self.resume_card = LastAnalysisCard()
        self.resume_card.clicked.connect(self.open_last_analysis)
        self.resume_card.set_meta(self.last_analysis.meta())
        layout.addWidget(self.resume_card)

        layout.addSpacing(12)
        prompt = QLabel("O QUE VOCÊ QUER FAZER?")
        prompt.setStyleSheet("color:#7A879D;font-size:11px;font-weight:900;letter-spacing:1.5px;")
        layout.addWidget(prompt)

        cards = QHBoxLayout()
        cards.setSpacing(20)
        analysis_card = FeatureCard(
            "📊", "Nova análise",
            f"Cruze estoque e vendas de até {len(STORES)} lojas e gere o dashboard com faturamento, "
            "giro, margem e ruptura.",
            "CRIAR ANÁLISE", "#2F5BEA", primary=True,
        )
        analysis_card.clicked.connect(lambda: self.stack.setCurrentWidget(self.analysis))
        stock_card = FeatureCard(
            "📦", "Explorar estoque",
            "Navegue por grupo e subclasse e cadastre, edite ou remova produtos do catálogo.",
            "ABRIR ESTOQUE", "#08A88F",
        )
        stock_card.clicked.connect(lambda: self.open_stock_explorer())
        self.alerts_card = FeatureCard(
            "🔔", "Alertas de estoque",
            "Defina o estoque mínimo por produto e loja e veja o que precisa de reposição.",
            "CONFIGURAR ALERTAS", "#E85D8A",
        )
        self.alerts_card.clicked.connect(lambda: self.open_stock_alerts())
        import_card = FeatureCard(
            "📥", "Importar cadastro",
            "Envie um Excel com código, grupo e subclasse e os produtos entram no catálogo automaticamente.",
            "IMPORTAR EXCEL", "#E8742A",
        )
        import_card.clicked.connect(lambda: self.import_catalog())
        for card in (analysis_card, stock_card, self.alerts_card, import_card):
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        self.refresh_alerts_tag()

        layout.addSpacing(10)
        chips = QHBoxLayout()
        chips.setSpacing(10)
        self.stat_chips = {}
        for key in ("codigos", "grupos", "subclasses", "lojas"):
            chip = QLabel()
            chip.setStyleSheet(
                "background:#FFFFFF;border:1px solid #DCE6F3;border-radius:14px;"
                "padding:8px 14px;color:#40516E;font-size:12px;font-weight:800;"
            )
            self.stat_chips[key] = chip
            chips.addWidget(chip)
        chips.addStretch()
        layout.addLayout(chips)
        layout.addStretch()

        footer = QLabel("Catálogo oficial Mix Moda")
        footer.setObjectName("Muted")
        layout.addWidget(footer)
        self.refresh_footer()
        return widget

    def refresh_footer(self):
        meta = self.catalog.get("meta", {})
        values = {
            "codigos": f"🏷️  {br_number(meta.get('total_produtos_unicos_por_codigo', 0), 0)} códigos",
            "grupos": f"🗂️  {br_number(meta.get('total_grupos', 0), 0)} grupos",
            "subclasses": f"🧩  {br_number(meta.get('total_subclasses', 0), 0)} subclasses",
            "lojas": f"🏬  {len(STORES)} lojas",
        }
        for key, text in values.items():
            self.stat_chips[key].setText(text)

    def refresh_alerts_tag(self):
        try:
            count = len(self.alert_store.load_rules())
        except (OSError, ValueError):
            count = 0
        self.alerts_card.set_tag(f"{count} REGRA{'S' if count != 1 else ''} ATIVA{'S' if count != 1 else ''}" if count else "")

    def open_stock_explorer(self):
        if self.stock_explorer is None:
            self.stock_explorer = StockExplorerPage(
                self.catalog,
                self.catalog_path,
                on_home=self.open_home,
                on_catalog_changed=self.catalog_changed,
            )
            self.stack.addWidget(self.stock_explorer)
        else:
            self.stock_explorer.reset()
        self.stack.setCurrentWidget(self.stock_explorer)

    def import_catalog(self):
        from ui.catalog_import import import_catalog_excel
        if import_catalog_excel(self, self.catalog, self.catalog_path, self.catalog_changed) and self.stock_explorer is not None:
            self.stock_explorer.reset()

    def catalog_changed(self):
        """O catálogo foi editado: a classificação usada nas próximas análises é refeita."""
        self.classification = classification_payload(self.catalog)
        self.refresh_footer()

    def open_stock_alerts(self):
        try:
            from ui.stock_alerts import StockAlertRulesDialog  # rapidfuzz/openpyxl só quando abre
            dialog = StockAlertRulesDialog(self.catalog, self.alert_store, self)
            dialog.exec()
            self.refresh_alerts_tag()
        except Exception as error:
            show_message(
                self,
                "critical",
                "Não foi possível abrir as regras",
                f"O formulário de alertas encontrou um erro.\n\n{type(error).__name__}: {error}",
            )

    def open_home(self):
        if self.resume_card.has_analysis():
            self.resume_card.set_meta(self.resume_card.meta())  # atualiza "hoje/ontem às"
        self.stack.setCurrentWidget(self.home)

    def open_last_analysis(self):
        meta = self.resume_card.meta()
        # A análise salva é a que já está aberta nesta sessão: só volta para ela.
        if self.dashboard is not None and meta and meta.get("id") == self.dashboard_id:
            self.stack.setCurrentWidget(self.dashboard)
            return
        self.resume_card.set_loading(True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        # Deixa o botão mostrar "ABRINDO…" antes do trabalho pesado começar.
        QTimer.singleShot(0, self._load_last_analysis)

    def _load_last_analysis(self):
        try:
            frame, period, audit, meta = self.last_analysis.load()
            self.show_dashboard(frame, period, audit, meta["id"])
        except LastAnalysisError as error:
            QApplication.restoreOverrideCursor()
            self.resume_card.set_meta(self.last_analysis.meta())
            show_message(self, "warning", "Não foi possível abrir a última análise", str(error))
            return
        except Exception as error:
            QApplication.restoreOverrideCursor()
            self.resume_card.set_loading(False)
            show_message(
                self, "critical", "Não foi possível abrir a última análise",
                "O dashboard encontrou um erro ao montar a análise salva. Gere uma nova análise.\n\n"
                f"{type(error).__name__}: {error}",
            )
            print(traceback.format_exc())
            return
        QApplication.restoreOverrideCursor()
        self.resume_card.set_loading(False)

    def show_dashboard(self, frame, period, audit, analysis_id=None):
        from ui.dashboard_page import DashboardPage
        page = DashboardPage(
            frame,
            period,
            audit,
            on_home=self.open_home,
            alert_store=self.alert_store,
            catalog=self.catalog,
        )
        # Descarta o dashboard anterior: cada um carrega vários gráficos e,
        # sem isso, a memória cresce a cada análise gerada.
        if self.dashboard is not None:
            self.stack.removeWidget(self.dashboard)
            self.dashboard.deleteLater()
        self.dashboard = page
        self.dashboard_id = analysis_id
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)

    def generate(self, info):
        # Módulos pesados (pandas, gráficos, PDF) só são carregados aqui, para a
        # tela inicial abrir rápido. O app.py já os pré-carrega em segundo plano.
        import pandas as pd
        from core.loader import load_stock, load_sales
        from core.matcher import build_analysis
        try:
            frames = []
            audits = []
            for store_info in info["lojas"]:
                stock = load_stock(store_info["estoque_path"])
                sales = load_sales(store_info["vendas_path"])
                config = AnalysisConfig(
                    loja=store_info["loja"],
                    data_inicio=info["data_inicio"],
                    data_fim=info["data_fim"],
                    estoque_path=store_info["estoque_path"],
                    vendas_path=store_info["vendas_path"],
                )
                frame, audit = build_analysis(
                    stock, sales, self.catalog, store_info["loja"], config, self.classification
                )
                frames.append(frame)
                audits.append(audit)

            frame = (
                pd.concat([item for item in frames if not item.empty], ignore_index=True)
                if any(not item.empty for item in frames)
                else pd.DataFrame()
            )
            if frame.empty:
                show_message(
                    self,
                    "warning",
                    "Sem dados",
                    "Nenhum produto válido permaneceu após limpeza e cruzamento.",
                )
                return

            audit = {}
            audit_keys = set().union(*(item.keys() for item in audits))
            for key in audit_keys:
                if key == "vendas_sem_correspondencia_itens":
                    audit[key] = [row for item in audits for row in item.get(key, [])]
                else:
                    audit[key] = sum(item.get(key, 0) for item in audits)

            snapshot_columns = [
                "codigo_barras", "descricao", "quantidade_estoque", "preco_venda", "loja"
            ]
            self.alert_store.save_snapshot(frame[snapshot_columns].to_dict("records"))

            period = (info["data_inicio"], info["data_fim"])
            analysis_id = self.save_last_analysis(frame, period, audit, info["lojas"])
            self.show_dashboard(frame, period, audit, analysis_id)
        except Exception as error:
            details = traceback.format_exc()
            show_message(
                self,
                "critical",
                "Erro ao gerar análise",
                f"Não foi possível processar os arquivos.\n\n{type(error).__name__}: {error}\n\n"
                "Verifique se os arquivos são XLS/XLSX válidos e se seguem o layout da Mix Moda.",
            )
            print(details)

    def save_last_analysis(self, frame, period, audit, stores):
        """Guarda a análise para o card da tela inicial; uma falha aqui não impede o dashboard."""
        try:
            meta = self.last_analysis.save(frame, period, audit, [s["loja"] for s in stores])
        except Exception as error:
            print(f"Não foi possível salvar a última análise: {type(error).__name__}: {error}")
            return None
        self.resume_card.set_meta(meta)
        return meta["id"]

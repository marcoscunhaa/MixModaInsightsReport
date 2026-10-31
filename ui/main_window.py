from pathlib import Path
import traceback

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.catalog_store import classification_payload, load_catalog
from core.models import AnalysisConfig
from core.stock_alerts import StockAlertStore
from ui.analysis_page import AnalysisPage
from ui.stock_explorer import StockExplorerPage
from ui.widgets import FeatureCard
from core.stores import STORES
from ui.window_chrome import install_mac_window_chrome, show_message
from ui.styles import APP_QSS
from utils.formatting import fmt_number


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
        subtitle = QLabel("An executive hub to understand stock, sales, sell-through, stockouts and performance by store.")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(18)
        prompt = QLabel("WHAT DO YOU WANT TO DO?")
        prompt.setStyleSheet("color:#7A879D;font-size:11px;font-weight:900;letter-spacing:1.5px;")
        layout.addWidget(prompt)

        cards = QHBoxLayout()
        cards.setSpacing(20)
        analysis_card = FeatureCard(
            "📊", "New analysis",
            f"Match stock and sales from up to {len(STORES)} stores and build a dashboard with revenue, "
            "sell-through, margin and stockouts.",
            "CREATE ANALYSIS", "#2F5BEA", primary=True,
        )
        analysis_card.clicked.connect(lambda: self.stack.setCurrentWidget(self.analysis))
        stock_card = FeatureCard(
            "📦", "Explore stock",
            "Browse by group and subclass and add, edit or remove products from the catalog.",
            "OPEN STOCK", "#08A88F",
        )
        stock_card.clicked.connect(lambda: self.open_stock_explorer())
        self.alerts_card = FeatureCard(
            "🔔", "Stock alerts",
            "Set the minimum stock per product and store and see what needs restocking.",
            "SET UP ALERTS", "#E85D8A",
        )
        self.alerts_card.clicked.connect(lambda: self.open_stock_alerts())
        for card in (analysis_card, stock_card, self.alerts_card):
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

        footer = QLabel("Official Mix Moda catalog")
        footer.setObjectName("Muted")
        layout.addWidget(footer)
        self.refresh_footer()
        return widget

    def refresh_footer(self):
        meta = self.catalog.get("meta", {})
        values = {
            "codigos": f"🏷️  {fmt_number(meta.get('total_produtos_unicos_por_codigo', 0), 0)} barcodes",
            "grupos": f"🗂️  {fmt_number(meta.get('total_grupos', 0), 0)} groups",
            "subclasses": f"🧩  {fmt_number(meta.get('total_subclasses', 0), 0)} subclasses",
            "lojas": f"🏬  {len(STORES)} stores",
        }
        for key, text in values.items():
            self.stat_chips[key].setText(text)

    def refresh_alerts_tag(self):
        try:
            count = len(self.alert_store.load_rules())
        except (OSError, ValueError):
            count = 0
        self.alerts_card.set_tag(f"{count} ACTIVE RULE{'S' if count != 1 else ''}" if count else "")

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

    def catalog_changed(self):
        """The catalog was edited: rebuild the classification used by the next analyses."""
        self.classification = classification_payload(self.catalog)
        self.refresh_footer()

    def open_stock_alerts(self):
        try:
            from ui.stock_alerts import StockAlertRulesDialog  # load rapidfuzz/openpyxl only when opened
            dialog = StockAlertRulesDialog(self.catalog, self.alert_store, self)
            dialog.exec()
            self.refresh_alerts_tag()
        except Exception as error:
            show_message(
                self,
                "critical",
                "Could not open the rules",
                f"The alerts form ran into an error.\n\n{type(error).__name__}: {error}",
            )

    def open_home(self):
        self.stack.setCurrentWidget(self.home)

    def generate(self, info):
        # Heavy modules (pandas, charts, PDF) are only loaded here so the home
        # screen opens fast. app.py already preloads them in the background.
        import pandas as pd
        from core.loader import load_stock, load_sales
        from core.matcher import build_analysis
        from ui.dashboard_page import DashboardPage
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
                    "No data",
                    "No valid product remained after cleaning and matching.",
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

            page = DashboardPage(
                frame,
                (info["data_inicio"], info["data_fim"]),
                audit,
                on_home=self.open_home,
                alert_store=self.alert_store,
            )
            # Discard the previous dashboard: each one holds several charts and,
            # without this, memory grows with every analysis.
            if self.dashboard is not None:
                self.stack.removeWidget(self.dashboard)
                self.dashboard.deleteLater()
            self.dashboard = page
            self.stack.addWidget(page)
            self.stack.setCurrentWidget(page)
        except Exception as error:
            details = traceback.format_exc()
            show_message(
                self,
                "critical",
                "Error generating the analysis",
                f"Could not process the files.\n\n{type(error).__name__}: {error}\n\n"
                "Check that the files are valid XLS/XLSX and follow the Mix Moda layout.",
            )
            print(details)

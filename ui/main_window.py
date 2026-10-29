from pathlib import Path
import traceback

import pandas as pd
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.catalog_store import load_catalog, load_classification_from_catalog
from core.loader import load_stock, load_sales
from core.matcher import build_analysis, load_classification
from core.models import AnalysisConfig
from core.stock_alerts import StockAlertStore
from ui.analysis_page import AnalysisPage
from ui.dashboard_page import DashboardPage
from ui.stock_alerts import StockAlertRulesDialog
from ui.stock_explorer import StockExplorerPage
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
        self.classification = load_classification_from_catalog(self.catalog, load_classification)

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


    def home_page(self):
        widget = QWidget()
        widget.setObjectName("Shell")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(90, 80, 90, 70)
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

        actions = QHBoxLayout()
        analysis_button = QPushButton("CRIAR NOVA ANÁLISE  →")
        analysis_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.analysis))
        actions.addWidget(analysis_button)
        stock_button = QPushButton("EXPLORAR ESTOQUE")
        stock_button.setObjectName("Secondary")
        stock_button.clicked.connect(lambda: self.open_stock_explorer())
        actions.addWidget(stock_button)
        alerts_button = QPushButton("CONFIGURAR ALERTAS")
        alerts_button.setObjectName("Secondary")
        alerts_button.clicked.connect(lambda: self.open_stock_alerts())
        actions.addWidget(alerts_button)
        actions.addStretch()
        layout.addLayout(actions)

        layout.addStretch()

        self.footer = QLabel()
        self.footer.setObjectName("Muted")
        self.refresh_footer()
        layout.addWidget(self.footer)
        return widget

    def refresh_footer(self):
        meta = self.catalog.get("meta", {})
        self.footer.setText(
            f"Catálogo oficial • {br_number(meta.get('total_produtos_unicos_por_codigo', 0), 0)} códigos "
            f"• {meta.get('total_grupos', 0)} grupos • {meta.get('total_subclasses', 0)} subclasses"
        )

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
        """O catálogo foi editado: a classificação usada nas próximas análises é refeita."""
        self.classification = load_classification_from_catalog(self.catalog, load_classification)
        self.refresh_footer()

    def open_stock_alerts(self):
        try:
            dialog = StockAlertRulesDialog(self.catalog, self.alert_store, self)
            dialog.exec()
        except Exception as error:
            show_message(
                self,
                "critical",
                "Não foi possível abrir as regras",
                f"O formulário de alertas encontrou um erro.\n\n{type(error).__name__}: {error}",
            )

    def open_home(self):
        self.stack.setCurrentWidget(self.home)

    def generate(self, info):
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

            page = DashboardPage(
                frame,
                (info["data_inicio"], info["data_fim"]),
                audit,
                on_home=self.open_home,
                alert_store=self.alert_store,
            )
            self.stack.addWidget(page)
            self.stack.setCurrentWidget(page)
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

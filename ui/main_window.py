from pathlib import Path
import traceback

import pandas as pd
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
from ui.catalog_page import CatalogPage
from ui.dashboard_page import DashboardPage
from ui.stock_alerts import StockAlertNotificationDialog, StockAlertRulesDialog
from ui.styles import APP_QSS
from utils.formatting import br_number


class MainWindow(QMainWindow):
    def __init__(self, catalog_path, user_data_dir=None):
        super().__init__()
        self.setWindowTitle("Mix Moda Insights")
        self.resize(1580, 980)
        self.setStyleSheet(APP_QSS)

        self.catalog = load_catalog(catalog_path)
        self.classification = load_classification_from_catalog(self.catalog, load_classification)

        data_dir = Path(user_data_dir) if user_data_dir else Path(catalog_path).resolve().parent
        self.alert_store = StockAlertStore(
            data_dir / "stock_alert_rules.json",
            data_dir / "stock_alert_snapshot.json",
        )

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.home = self.home_page()
        self.analysis = AnalysisPage()
        self.analysis.generate.connect(self.generate)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.analysis)

        # Reuse the last analyzed stock snapshot so rules can notify on app launch.
        QTimer.singleShot(350, self.notify_latest_stock_alerts)

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
        catalog_button = QPushButton("EXPLORAR CATÁLOGO")
        catalog_button.setObjectName("Secondary")
        catalog_button.clicked.connect(self.open_catalog)
        actions.addWidget(catalog_button)
        alerts_button = QPushButton("ALERTAS DE ESTOQUE")
        alerts_button.setObjectName("Secondary")
        alerts_button.clicked.connect(self.open_stock_alerts)
        actions.addWidget(alerts_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

        meta = self.catalog.get("meta", {})
        footer = QLabel(
            f"Catálogo oficial • {br_number(meta.get('total_produtos_unicos_por_codigo', 0), 0)} códigos "
            f"• {meta.get('total_grupos', 0)} grupos • {meta.get('total_subclasses', 0)} subclasses"
        )
        footer.setObjectName("Muted")
        layout.addWidget(footer)
        return widget

    def open_catalog(self):
        if not hasattr(self, "catpage"):
            self.catpage = CatalogPage(self.catalog)
            self.stack.addWidget(self.catpage)
        self.stack.setCurrentWidget(self.catpage)

    def open_stock_alerts(self, notify_after=True):
        dialog = StockAlertRulesDialog(self.catalog, self.alert_store, self)
        dialog.exec()
        if notify_after:
            self.notify_latest_stock_alerts()

    def notify_latest_stock_alerts(self):
        snapshot = self.alert_store.load_snapshot()
        alerts = self.alert_store.evaluate(snapshot.get("rows", []))
        if not alerts:
            return
        dialog = StockAlertNotificationDialog(alerts, snapshot.get("updated_at"), self)
        dialog.exec()
        if dialog.manage_requested:
            self.open_stock_alerts(notify_after=False)

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
                QMessageBox.warning(
                    self,
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

            # Save the valid stock currently being analyzed for next launch's alerts.
            snapshot_columns = ["codigo_barras", "descricao", "quantidade_estoque", "loja"]
            self.alert_store.save_snapshot(frame[snapshot_columns].to_dict("records"))

            page = DashboardPage(
                frame,
                (info["data_inicio"], info["data_fim"]),
                audit,
                on_manage_alerts=self.open_stock_alerts,
            )
            self.stack.addWidget(page)
            self.stack.setCurrentWidget(page)
            self.notify_latest_stock_alerts()
        except Exception as error:
            details = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Erro ao gerar análise",
                f"Não foi possível processar os arquivos.\n\n{type(error).__name__}: {error}\n\n"
                "Verifique se os arquivos são XLS/XLSX válidos e se seguem o layout da Mix Moda.",
            )
            print(details)

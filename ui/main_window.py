from pathlib import Path
import traceback

import pandas as pd
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
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
from core.whatsapp import WhatsAppCloudClient
from ui.analysis_page import AnalysisPage
from ui.catalog_page import CatalogPage
from ui.dashboard_page import DashboardPage
from ui.stock_alerts import StockAlertRulesDialog
from ui.styles import APP_QSS
from utils.formatting import br_number


class _WhatsAppSendSignals(QObject):
    finished = Signal(object, object)


class _WhatsAppSendWorker(QRunnable):
    def __init__(self, client, alerts):
        super().__init__()
        self.client = client
        self.alerts = alerts
        self.signals = _WhatsAppSendSignals()

    def run(self):
        try:
            message_ids = self.client.send_stock_alerts(self.alerts)
            self.signals.finished.emit(message_ids, None)
        except Exception as error:
            self.signals.finished.emit(None, str(error))


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
        self.whatsapp_client = WhatsAppCloudClient(self.alert_store)
        self._alert_send_pool = QThreadPool.globalInstance()
        self._alert_send_worker = None
        self._alert_sending = False
        self._pending_alerts = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.home = self.home_page()
        self.analysis = AnalysisPage()
        self.analysis.generate.connect(self.generate)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.analysis)

        # Reuse the last analyzed stock snapshot for automatic WhatsApp alerts at launch.
        QTimer.singleShot(350, self.refresh_alert_status)
        QTimer.singleShot(350, self.send_latest_stock_alerts)

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
        alerts_button = QPushButton("CONFIGURAR ALERTAS")
        alerts_button.setObjectName("Secondary")
        alerts_button.clicked.connect(self.open_stock_alerts)
        actions.addWidget(alerts_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.alert_status = QLabel()
        self.alert_status.setObjectName("Muted")
        layout.addWidget(self.alert_status)
        layout.addStretch()

        meta = self.catalog.get("meta", {})
        footer = QLabel(
            f"Catálogo oficial • {br_number(meta.get('total_produtos_unicos_por_codigo', 0), 0)} códigos "
            f"• {meta.get('total_grupos', 0)} grupos • {meta.get('total_subclasses', 0)} subclasses"
        )
        footer.setObjectName("Muted")
        layout.addWidget(footer)
        return widget

    def refresh_alert_status(self):
        settings = self.alert_store.load_settings()
        missing = self.whatsapp_client.missing_configuration()
        rule_count = len(self.alert_store.load_rules())
        if not rule_count:
            text = "Alertas de estoque: nenhuma regra configurada."
        elif missing:
            text = "Alertas salvos; para receber no WhatsApp, complete a configuração em CONFIGURAR ALERTAS."
        else:
            text = f"WhatsApp configurado • {rule_count} regra(s) de estoque ativa(s)."
        self.alert_status.setText(text)
        self.alert_status.setToolTip(
            f"Destinatário salvo: {settings.get('whatsapp_recipient', '') or 'não informado'}"
        )

    def open_catalog(self):
        if not hasattr(self, "catpage"):
            self.catpage = CatalogPage(self.catalog)
            self.stack.addWidget(self.catpage)
        self.stack.setCurrentWidget(self.catpage)

    def open_stock_alerts(self):
        dialog = StockAlertRulesDialog(self.catalog, self.alert_store, self)
        dialog.exec()
        self.refresh_alert_status()
        self.send_latest_stock_alerts()

    def send_latest_stock_alerts(self):
        if self._alert_sending:
            return
        snapshot = self.alert_store.load_snapshot()
        alerts = self.alert_store.evaluate(snapshot.get("rows", []))
        pending = self.alert_store.unsent_alerts(alerts)
        if not pending or self.whatsapp_client.missing_configuration():
            return

        self._pending_alerts = pending
        self._alert_sending = True
        worker = _WhatsAppSendWorker(self.whatsapp_client, pending)
        worker.signals.finished.connect(self._on_whatsapp_send_finished)
        self._alert_send_worker = worker
        self._alert_send_pool.start(worker)

    def _on_whatsapp_send_finished(self, message_ids, error):
        self._alert_sending = False
        self._alert_send_worker = None
        if error:
            QMessageBox.warning(
                self,
                "Falha no envio pelo WhatsApp",
                f"A lista de estoque crítico não foi enviada.\n\n{error}\n\n"
                "Confira a conexão, o template aprovado e as credenciais da Meta.",
            )
            return
        self.alert_store.mark_alerts_sent(self._pending_alerts)
        self._pending_alerts = []
        self.refresh_alert_status()

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

            snapshot_columns = [
                "codigo_barras", "descricao", "quantidade_estoque", "preco_venda", "loja"
            ]
            self.alert_store.save_snapshot(frame[snapshot_columns].to_dict("records"))

            page = DashboardPage(
                frame,
                (info["data_inicio"], info["data_fim"]),
                audit,
                on_home=self.open_home,
            )
            self.stack.addWidget(page)
            self.stack.setCurrentWidget(page)
            self.send_latest_stock_alerts()
        except Exception as error:
            details = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Erro ao gerar análise",
                f"Não foi possível processar os arquivos.\n\n{type(error).__name__}: {error}\n\n"
                "Verifique se os arquivos são XLS/XLSX válidos e se seguem o layout da Mix Moda.",
            )
            print(details)

"""Dialogs for configuring and reviewing persistent stock alerts."""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.stock_alerts import StockAlertStore
from ui.analysis_page import STORES
from utils.normalization import normalize_barcode, normalize_text


class StockAlertRulesDialog(QDialog):
    def __init__(self, catalog, alert_store, parent=None):
        super().__init__(parent)
        self.catalog = catalog or {}
        self.alert_store = alert_store
        self.products = self.catalog.get("produtos", [])
        self.selected_product = None

        self.setWindowTitle("Regras de alerta de estoque")
        self.resize(1120, 800)
        self.setMinimumSize(940, 680)
        self.setStyleSheet("""
            QDialog { background: #F4F7FC; }
            QLabel#pageTitle { color: #14284B; font-size: 23px; font-weight: 900; }
            QLabel#muted { color: #718097; font-size: 11px; }
            QLabel#sectionTitle { color: #14284B; font-size: 14px; font-weight: 850; }
            QFrame#panel { background: #FFFFFF; border: 1px solid #DCE5F2; border-radius: 16px; }
            QListWidget, QTableWidget { background: #FFFFFF; border: 1px solid #DCE5F2; border-radius: 10px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #EDF1F7; }
            QListWidget::item:selected { background: #EAF0FF; color: #17326F; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 22)
        root.setSpacing(12)

        title = QLabel("ALERTAS DE ESTOQUE")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        intro = QLabel(
            "Escolha produtos e defina a faixa de unidades que deve gerar um aviso. "
            "As regras ficam salvas para as próximas aberturas do aplicativo."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        add_panel = QFrame()
        add_panel.setObjectName("panel")
        add_layout = QVBoxLayout(add_panel)
        add_layout.setContentsMargins(16, 14, 16, 16)
        add_layout.setSpacing(8)
        add_title = QLabel("Adicionar ou atualizar uma regra")
        add_title.setObjectName("sectionTitle")
        add_layout.addWidget(add_title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nome do produto ou código de barras...")
        self.search.textChanged.connect(self.refresh_products)
        add_layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.setMaximumHeight(150)
        self.results.currentItemChanged.connect(self.select_product)
        add_layout.addWidget(self.results)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.selected_label = QLabel("Selecione um produto na lista.")
        self.selected_label.setObjectName("muted")
        self.selected_label.setWordWrap(True)
        form.addWidget(self.selected_label, 0, 0, 1, 4)

        self.store = QComboBox()
        self.store.addItem("Todas as lojas", "*")
        for store in STORES:
            self.store.addItem(store, store)

        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100000)
        self.minimum.setValue(0)
        self.maximum = QSpinBox()
        self.maximum.setRange(0, 100000)
        self.maximum.setValue(3)

        form.addWidget(QLabel("Aplicar em"), 1, 0)
        form.addWidget(self.store, 1, 1)
        form.addWidget(QLabel("Estoque mínimo"), 1, 2)
        form.addWidget(self.minimum, 1, 3)
        form.addWidget(QLabel("Estoque máximo"), 1, 4)
        form.addWidget(self.maximum, 1, 5)
        add_layout.addLayout(form)

        action_row = QHBoxLayout()
        self.status = QLabel("Exemplo: avisar quando o estoque ficar entre 0 e 3 unidades.")
        self.status.setObjectName("muted")
        action_row.addWidget(self.status, 1)
        self.save_button = QPushButton("＋  SALVAR REGRA")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_rule)
        action_row.addWidget(self.save_button)
        add_layout.addLayout(action_row)
        root.addWidget(add_panel)

        rules_panel = QFrame()
        rules_panel.setObjectName("panel")
        rules_layout = QVBoxLayout(rules_panel)
        rules_layout.setContentsMargins(16, 14, 16, 14)
        rules_layout.setSpacing(8)
        rules_title = QLabel("Regras salvas")
        rules_title.setObjectName("sectionTitle")
        rules_layout.addWidget(rules_title)

        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(["Produto", "Código", "Loja", "Faixa de estoque", ""])
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setAlternatingRowColors(True)
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            self.rules_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        rules_layout.addWidget(self.rules_table, 1)
        root.addWidget(rules_panel, 1)

        footer = QHBoxLayout()
        hint = QLabel(
            "Os avisos são avaliados após cada análise e, ao abrir o app, com os dados da última análise."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        footer.addWidget(hint, 1)
        close_button = QPushButton("FECHAR")
        close_button.setObjectName("Ghost")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self.refresh_rules()
        self.refresh_products("")

    def refresh_products(self, text):
        self.results.clear()
        self.selected_product = None
        self.save_button.setEnabled(False)
        query = str(text).strip()
        if len(query) < 2:
            self.selected_label.setText("Digite ao menos 2 caracteres do nome ou do código para pesquisar.")
            return

        normalized_query = normalize_text(query)
        normalized_code_query = normalize_barcode(query)
        matches = []
        for product in self.products:
            description = str(product.get("descricao", ""))
            barcode = str(product.get("codigo_barras", ""))
            if (
                normalized_query in normalize_text(description)
                or query in barcode
                or (
                    normalized_code_query
                    and normalized_code_query in normalize_barcode(barcode)
                )
            ):
                matches.append(product)

        for product in matches[:150]:
            description = str(product.get("descricao", "Produto"))
            barcode = str(product.get("codigo_barras", ""))
            group = str(product.get("grupo", ""))
            subclass = str(product.get("subclasse", ""))
            item = QListWidgetItem(
                f"{description}  •  {barcode}\n{group}  /  {subclass}"
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                (normalize_barcode(barcode), normalize_text(description)),
            )
            self.results.addItem(item)

        if not matches:
            self.selected_label.setText("Nenhum produto encontrado. Tente outro nome ou código.")
        elif len(matches) > 150:
            self.selected_label.setText(f"{len(matches)} produtos encontrados; exibindo os primeiros 150.")
        else:
            self.selected_label.setText(f"{len(matches)} produtos encontrados; selecione um para configurar.")

    def select_product(self, current, previous):
        if current is None:
            self.selected_product = None
            self.save_button.setEnabled(False)
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        self.selected_product = next(
            (
                product for product in self.products
                if (
                    normalize_barcode(product.get("codigo_barras")),
                    normalize_text(product.get("descricao")),
                ) == key
            ),
            None,
        )
        if self.selected_product:
            self.selected_label.setText(
                f"Selecionado: {self.selected_product.get('descricao', '')} "
                f"• Código {self.selected_product.get('codigo_barras', '')}"
            )
            self.save_button.setEnabled(True)

    def save_rule(self):
        if not self.selected_product:
            return
        minimum = self.minimum.value()
        maximum = self.maximum.value()
        if maximum < minimum:
            QMessageBox.warning(self, "Faixa inválida", "O estoque máximo precisa ser igual ou maior que o mínimo.")
            return
        product = self.selected_product
        try:
            self.alert_store.upsert_rule({
                "codigo_barras": product.get("codigo_barras"),
                "descricao": product.get("descricao"),
                "loja": self.store.currentData(),
                "estoque_minimo": minimum,
                "estoque_maximo": maximum,
            })
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Não foi possível salvar", str(error))
            return
        self.status.setText("Regra salva. Ela será aplicada às próximas análises e na próxima abertura.")
        self.refresh_rules()

    def refresh_rules(self):
        rules = self.alert_store.load_rules()
        self.rules_table.setRowCount(len(rules))
        for row_index, rule in enumerate(rules):
            store = rule.get("loja", "*")
            store_label = "Todas as lojas" if store == "*" else store
            values = [
                str(rule.get("descricao", "")),
                str(rule.get("codigo_barras", "")),
                store_label,
                f"{rule.get('estoque_minimo', 0)} a {rule.get('estoque_maximo', 0)} unidades",
            ]
            for column, value in enumerate(values):
                self.rules_table.setItem(row_index, column, QTableWidgetItem(value))
            remove = QPushButton("Remover")
            remove.setObjectName("Danger")
            remove.clicked.connect(
                lambda checked=False, rule_id=rule.get("id"): self.remove_rule(rule_id)
            )
            self.rules_table.setCellWidget(row_index, 4, remove)
            self.rules_table.setRowHeight(row_index, 42)

    def remove_rule(self, rule_id):
        try:
            self.alert_store.remove_rule(rule_id)
        except OSError as error:
            QMessageBox.critical(self, "Não foi possível remover", str(error))
            return
        self.refresh_rules()


class StockAlertNotificationDialog(QDialog):
    def __init__(self, alerts, updated_at=None, parent=None):
        super().__init__(parent)
        self.manage_requested = False
        self.setWindowTitle("Alertas de estoque")
        self.resize(980, 650)
        self.setMinimumSize(820, 520)
        self.setStyleSheet("""
            QDialog { background: #F4F7FC; }
            QLabel#title { color: #14284B; font-size: 24px; font-weight: 900; }
            QLabel#subtitle { color: #718097; font-size: 12px; }
            QFrame#banner { background: #FFF4E7; border: 1px solid #F4D8B5; border-left: 5px solid #E6A92E; border-radius: 14px; }
            QTableWidget { background: #FFFFFF; border: 1px solid #DCE5F2; border-radius: 10px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        banner = QFrame()
        banner.setObjectName("banner")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("Atenção ao estoque")
        title.setObjectName("title")
        banner_layout.addWidget(title)
        subtitle = QLabel(
            f"{len(alerts)} ocorrência(s) estão na faixa crítica configurada."
        )
        subtitle.setObjectName("subtitle")
        banner_layout.addWidget(subtitle)
        if updated_at:
            try:
                timestamp = datetime.fromisoformat(updated_at).astimezone().strftime("%d/%m/%Y às %H:%M")
                freshness = f"Base de estoque da última análise: {timestamp}"
            except (TypeError, ValueError):
                freshness = "Baseada no estoque da última análise."
            age = QLabel(freshness)
            age.setObjectName("subtitle")
            banner_layout.addWidget(age)
        root.addWidget(banner)

        table = QTableWidget(len(alerts), 5)
        table.setHorizontalHeaderLabels(["Produto", "Código de barras", "Loja", "Estoque atual", "Faixa configurada"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for row_index, alert in enumerate(alerts):
            values = [
                str(alert.get("descricao", "")),
                str(alert.get("codigo_barras", "")),
                str(alert.get("loja", "")),
                f"{float(alert.get('quantidade_estoque', 0)):g} un.",
                f"{alert.get('estoque_minimo', 0)}–{alert.get('estoque_maximo', 0)} un.",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_index, column, item)
            table.setRowHeight(row_index, 40)
        root.addWidget(table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        manage = QPushButton("GERENCIAR REGRAS")
        manage.setObjectName("Secondary")
        manage.clicked.connect(self._manage)
        footer.addWidget(manage)
        close = QPushButton("FECHAR")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    def _manage(self):
        self.manage_requested = True
        self.accept()

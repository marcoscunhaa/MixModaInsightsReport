"""Product search, persistent stock-alert rules, and WhatsApp settings."""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
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
    QFrame,
)
from rapidfuzz import fuzz

from core.stock_alerts import StockAlertStore
from ui.analysis_page import STORES
from utils.normalization import normalize_barcode, normalize_text


class StockAlertRulesDialog(QDialog):
    def __init__(self, catalog, alert_store, parent=None):
        super().__init__(parent)
        self.catalog = catalog or {}
        self.alert_store = alert_store
        self.products = self.catalog.get("produtos", [])
        self.products_by_key = {
            (
                normalize_barcode(product.get("codigo_barras")),
                normalize_text(product.get("descricao")),
            ): product
            for product in self.products
        }
        self.selected_product = None

        self.setWindowTitle("Regras de alerta de estoque")
        self.resize(1120, 850)
        self.setMinimumSize(940, 700)
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
            "Busque produtos pelo nome ou código, escolha uma faixa de estoque e informe "
            "o WhatsApp que receberá a lista dos produtos críticos."
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
        self.search.setPlaceholderText("Digite parte do nome (ex.: cueca cavada) ou do código de barras...")
        self.search.textChanged.connect(self.refresh_products)
        add_layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.setMaximumHeight(175)
        self.results.currentItemChanged.connect(self.select_product)
        add_layout.addWidget(self.results)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.selected_label = QLabel("Digite ao menos 2 caracteres para ver sugestões.")
        self.selected_label.setObjectName("muted")
        self.selected_label.setWordWrap(True)
        form.addWidget(self.selected_label, 0, 0, 1, 6)

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

        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("Ex.: +55 11 99999-9999")
        form.addWidget(QLabel("WhatsApp destinatário"), 2, 0)
        form.addWidget(self.recipient, 2, 1, 1, 5)
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

        whatsapp_panel = QFrame()
        whatsapp_panel.setObjectName("panel")
        whatsapp_layout = QVBoxLayout(whatsapp_panel)
        whatsapp_layout.setContentsMargins(16, 14, 16, 14)
        whatsapp_layout.setSpacing(7)
        whatsapp_title = QLabel("Conexão WhatsApp Business")
        whatsapp_title.setObjectName("sectionTitle")
        whatsapp_layout.addWidget(whatsapp_title)

        settings = self.alert_store.load_settings()
        self.phone_number_id = QLineEdit(str(settings.get("phone_number_id", "")))
        self.phone_number_id.setPlaceholderText("Phone Number ID do número remetente na Meta")
        self.template_name = QLineEdit(str(settings.get("template_name", "")))
        self.template_name.setPlaceholderText("Nome do template de mensagem aprovado")
        self.template_language = QLineEdit(str(settings.get("template_language", "pt_BR")))
        self.template_language.setPlaceholderText("pt_BR")
        self.access_token = QLineEdit()
        self.access_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.access_token.setPlaceholderText(
            "Token salvo no cofre do sistema; deixe vazio para manter"
            if self.alert_store.has_access_token()
            else "Token de acesso da Meta"
        )

        config_grid = QGridLayout()
        config_grid.setHorizontalSpacing(12)
        config_grid.setVerticalSpacing(7)
        config_grid.addWidget(QLabel("Phone Number ID"), 0, 0)
        config_grid.addWidget(self.phone_number_id, 0, 1)
        config_grid.addWidget(QLabel("Template aprovado"), 0, 2)
        config_grid.addWidget(self.template_name, 0, 3)
        config_grid.addWidget(QLabel("Idioma"), 0, 4)
        config_grid.addWidget(self.template_language, 0, 5)
        config_grid.addWidget(QLabel("Token de acesso"), 1, 0)
        config_grid.addWidget(self.access_token, 1, 1, 1, 5)
        whatsapp_layout.addLayout(config_grid)

        setup_hint = QLabel(
            "Use um template Utility aprovado pela Meta com um único campo de texto {{1}}. "
            "O token é guardado no cofre de credenciais do computador, não no JSON."
        )
        setup_hint.setObjectName("muted")
        setup_hint.setWordWrap(True)
        whatsapp_layout.addWidget(setup_hint)

        connection_row = QHBoxLayout()
        self.whatsapp_status = QLabel()
        self.whatsapp_status.setObjectName("muted")
        connection_row.addWidget(self.whatsapp_status, 1)
        save_connection = QPushButton("SALVAR CONFIGURAÇÃO")
        save_connection.setObjectName("Secondary")
        save_connection.clicked.connect(self.save_whatsapp_settings)
        connection_row.addWidget(save_connection)
        whatsapp_layout.addLayout(connection_row)
        root.addWidget(whatsapp_panel)
        self.refresh_connection_status()

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
            "Os avisos são enviados após cada análise e na abertura do app, usando os dados da última análise."
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

    def refresh_connection_status(self):
        missing = []
        settings = self.alert_store.load_settings()
        if not settings.get("whatsapp_recipient") and not self.recipient.text().strip():
            missing.append("destinatário")
        if not self.phone_number_id.text().strip():
            missing.append("Phone Number ID")
        if not self.template_name.text().strip():
            missing.append("template")
        if not self.alert_store.has_access_token() and not self.access_token.text().strip():
            missing.append("token")
        if missing:
            self.whatsapp_status.setText("Falta configurar: " + ", ".join(missing) + ".")
        else:
            self.whatsapp_status.setText("Configuração preenchida; mensagens serão enviadas quando houver alerta.")

    def _settings_payload(self):
        return {
            "whatsapp_recipient": self.recipient.text(),
            "phone_number_id": self.phone_number_id.text(),
            "template_name": self.template_name.text(),
            "template_language": self.template_language.text() or "pt_BR",
        }

    def save_whatsapp_settings(self):
        try:
            self.alert_store.save_settings(self._settings_payload(), self.access_token.text())
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.critical(self, "Não foi possível salvar", str(error))
            return
        self.access_token.clear()
        self.access_token.setPlaceholderText("Token salvo no cofre do sistema; deixe vazio para manter")
        self.whatsapp_status.setText("Configuração do WhatsApp salva.")
        self.refresh_connection_status()

    def refresh_products(self, text):
        self.results.clear()
        self.selected_product = None
        self.save_button.setEnabled(False)
        query = str(text).strip()
        if len(query) < 2:
            self.selected_label.setText("Digite ao menos 2 caracteres para ver sugestões.")
            return

        normalized_query = normalize_text(query)
        query_digits = normalize_barcode(query)
        code_search = bool(re.fullmatch(r"[\d\s./+-]+", query))
        matches = []
        for product in self.products:
            description = str(product.get("descricao", ""))
            normalized_description = normalize_text(description)
            barcode = str(product.get("codigo_barras", ""))
            normalized_barcode = normalize_barcode(barcode)

            if code_search and query_digits and query_digits in normalized_barcode:
                score = 1200 if normalized_barcode == query_digits else 1100
            elif normalized_query in normalized_description:
                score = 1000 - normalized_description.find(normalized_query)
            else:
                score = max(
                    fuzz.WRatio(normalized_query, normalized_description),
                    fuzz.token_set_ratio(normalized_query, normalized_description),
                    fuzz.partial_ratio(normalized_query, normalized_description) * 0.82,
                )
                if query_digits and query_digits in normalized_barcode:
                    score = max(score, 950)

            if score >= 48:
                matches.append((score, product))

        matches.sort(
            key=lambda item: (
                -item[0],
                normalize_text(item[1].get("descricao", "")),
                normalize_barcode(item[1].get("codigo_barras")),
            )
        )
        shown = matches[:60]
        for _, product in shown:
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
            self.selected_label.setText("Nenhum produto parecido encontrado. Tente outra palavra ou parte do código.")
        elif len(matches) > len(shown):
            self.selected_label.setText(
                f"{len(matches)} sugestões ordenadas por semelhança; exibindo as 60 mais próximas. Selecione uma."
            )
        else:
            self.selected_label.setText(f"{len(matches)} sugestões ordenadas; selecione o produto desejado.")

    def select_product(self, current, previous):
        if current is None:
            self.selected_product = None
            self.save_button.setEnabled(False)
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        self.selected_product = self.products_by_key.get(key)
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
            settings = self._settings_payload()
            self.alert_store.save_settings(settings)
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
        self.status.setText("Regra salva. O aviso será enviado quando a faixa for atingida.")
        self.refresh_connection_status()
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

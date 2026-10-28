"""Interface para configurar regras e consultar alertas de estoque."""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from rapidfuzz import fuzz

from core.stock_alerts import StockAlertStore
from ui.analysis_page import STORES
from utils.formatting import brl, br_number
from utils.normalization import normalize_barcode, normalize_text


PALETTE = """
QDialog { background:#F3F6FB; }
QLabel#eyebrow { color:#526FE3; font-size:10px; font-weight:900; letter-spacing:1px; }
QLabel#title { color:#14284B; font-size:24px; font-weight:900; }
QLabel#muted { color:#74829A; font-size:11px; }
QLabel#section { color:#192D50; font-size:13px; font-weight:900; }
QFrame#panel { background:#FFFFFF; border:1px solid #E0E7F1; border-radius:16px; }
QLineEdit, QComboBox, QSpinBox { background:#F8FAFD; border:1px solid #DCE4F0; border-radius:9px; padding:9px 10px; color:#233451; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:1px solid #5675E8; background:#FFFFFF; }
QListWidget, QTableWidget { background:#FFFFFF; border:1px solid #E2E8F1; border-radius:10px; }
QListWidget::item { padding:9px; border-bottom:1px solid #EEF1F6; }
QListWidget::item:selected { background:#EEF2FF; color:#18377C; }
"""


def _panel():
    frame = QFrame()
    frame.setObjectName("panel")
    return frame


class StockAlertRulesDialog(QDialog):
    def __init__(self, catalog, alert_store, parent=None):
        super().__init__(parent)
        self.catalog = catalog or {}
        self.alert_store = alert_store
        self.products = self.catalog.get("produtos", [])
        self.products_by_key = {
            (normalize_barcode(p.get("codigo_barras")), normalize_text(p.get("descricao"))): p
            for p in self.products
        }
        self.selected_product = None
        self.setWindowTitle("Regras de estoque • Mix Moda")
        self.resize(1050, 820)
        self.setMinimumSize(900, 700)
        self.setStyleSheet(PALETTE)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(13)
        root.addWidget(self._heading())
        root.addWidget(self._editor())
        root.addWidget(self._rules_panel(), 1)
        root.addLayout(self._footer())

        self.refresh_rules()
        self.refresh_products("")

    def _heading(self):
        box = QVBoxLayout()
        eyebrow = QLabel("GESTÃO INTELIGENTE DE ESTOQUE")
        eyebrow.setObjectName("eyebrow")
        box.addWidget(eyebrow)
        title = QLabel("Regras de estoque crítico")
        title.setObjectName("title")
        box.addWidget(title)
        subtitle = QLabel("Escolha os produtos importantes e defina quando o estoque deve chamar sua atenção.")
        subtitle.setObjectName("muted")
        box.addWidget(subtitle)
        wrapper = QWidget()
        wrapper.setLayout(box)
        return wrapper

    def _editor(self):
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        title = QLabel("Criar ou atualizar regra")
        title.setObjectName("section")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nome ou código de barras — ex.: cueca cavada")
        self.search.textChanged.connect(self.refresh_products)
        layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.setMaximumHeight(175)
        self.results.currentItemChanged.connect(self.select_product)
        layout.addWidget(self.results)

        self.selected_label = QLabel("Digite pelo menos 2 caracteres para encontrar um produto.")
        self.selected_label.setObjectName("muted")
        self.selected_label.setWordWrap(True)
        layout.addWidget(self.selected_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.addWidget(self._field_label("LOJA"), 0, 0)
        self.store = QComboBox()
        self.store.addItem("Todas as lojas", "*")
        for store in STORES:
            self.store.addItem(store, store)
        grid.addWidget(self.store, 1, 0)

        grid.addWidget(self._field_label("ESTOQUE MÍNIMO"), 0, 1)
        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100000)
        grid.addWidget(self.minimum, 1, 1)
        grid.addWidget(self._field_label("ESTOQUE MÁXIMO"), 0, 2)
        self.maximum = QSpinBox()
        self.maximum.setRange(0, 100000)
        self.maximum.setValue(3)
        grid.addWidget(self.maximum, 1, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        actions = QHBoxLayout()
        self.status = QLabel("O alerta aparece quando o estoque estiver entre os limites definidos.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        actions.addWidget(self.status, 1)
        self.save_button = QPushButton("＋  SALVAR REGRA")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_rule)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        return panel

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setStyleSheet("color:#8290A6;font-size:9px;font-weight:900;letter-spacing:0.6px;")
        return label

    def _rules_panel(self):
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 14)
        heading = QHBoxLayout()
        title = QLabel("Suas regras")
        title.setObjectName("section")
        heading.addWidget(title)
        heading.addStretch()
        self.rule_count = QLabel()
        self.rule_count.setObjectName("muted")
        heading.addWidget(self.rule_count)
        layout.addLayout(heading)

        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(["Produto", "Código", "Loja", "Limite de estoque", ""])
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setAlternatingRowColors(True)
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            self.rules_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.rules_table, 1)
        return panel

    def _footer(self):
        row = QHBoxLayout()
        note = QLabel("As regras ficam salvas neste computador e são verificadas com os dados da última análise.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        row.addWidget(note, 1)
        close = QPushButton("CONCLUÍDO")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        return row

    def refresh_products(self, text):
        self.results.clear()
        self.selected_product = None
        self.save_button.setEnabled(False)
        query = str(text).strip()
        if len(query) < 2:
            self.selected_label.setText("Digite pelo menos 2 caracteres para encontrar um produto.")
            return
        normalized_query = normalize_text(query)
        query_digits = normalize_barcode(query)
        code_search = bool(re.fullmatch(r"[\d\s./+-]+", query))
        matches = []
        for product in self.products:
            description = str(product.get("descricao", ""))
            normalized_description = normalize_text(description)
            barcode = normalize_barcode(product.get("codigo_barras"))
            if code_search and query_digits and query_digits in barcode:
                score = 1200 if barcode == query_digits else 1100
            elif normalized_query in normalized_description:
                score = 1000 - normalized_description.find(normalized_query)
            else:
                score = max(
                    fuzz.WRatio(normalized_query, normalized_description),
                    fuzz.token_set_ratio(normalized_query, normalized_description),
                    fuzz.partial_ratio(normalized_query, normalized_description) * 0.82,
                )
                if query_digits and query_digits in barcode:
                    score = max(score, 950)
            if score >= 48:
                matches.append((score, product))
        matches.sort(key=lambda pair: (-pair[0], normalize_text(pair[1].get("descricao", ""))))
        for _, product in matches[:60]:
            description = str(product.get("descricao", "Produto"))
            barcode = str(product.get("codigo_barras", ""))
            item = QListWidgetItem(f"{description}  •  {barcode}")
            item.setData(Qt.ItemDataRole.UserRole, (normalize_barcode(barcode), normalize_text(description)))
            self.results.addItem(item)
        if not matches:
            self.selected_label.setText("Nenhum produto encontrado. Tente outra palavra ou parte do código.")
        else:
            self.selected_label.setText(f"{len(matches)} produtos encontrados. Selecione o item para definir a regra.")

    def select_product(self, current, _previous):
        self.selected_product = None
        self.save_button.setEnabled(False)
        if current is None:
            return
        self.selected_product = self.products_by_key.get(current.data(Qt.ItemDataRole.UserRole))
        if self.selected_product:
            self.selected_label.setText(
                f"Selecionado: {self.selected_product.get('descricao', '')}  •  "
                f"Código {self.selected_product.get('codigo_barras', '')}"
            )
            self.save_button.setEnabled(True)

    def save_rule(self):
        if not self.selected_product:
            return
        minimum, maximum = self.minimum.value(), self.maximum.value()
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
        self.status.setText("Regra salva. Ela será verificada na próxima análise.")
        self.refresh_rules()

    def refresh_rules(self):
        rules = self.alert_store.load_rules()
        self.rule_count.setText(f"{len(rules)} regra(s) ativa(s)")
        self.rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            store = rule.get("loja", "*")
            values = [
                str(rule.get("descricao", "")), str(rule.get("codigo_barras", "")),
                "Todas as lojas" if store == "*" else store,
                f"{rule.get('estoque_minimo', 0)}–{rule.get('estoque_maximo', 0)} un.",
            ]
            for col, value in enumerate(values):
                self.rules_table.setItem(row, col, QTableWidgetItem(value))
            remove = QPushButton("Remover")
            remove.setObjectName("Danger")
            remove.clicked.connect(lambda checked=False, rule_id=rule.get("id"): self.remove_rule(rule_id))
            self.rules_table.setCellWidget(row, 4, remove)
            self.rules_table.setRowHeight(row, 40)

    def remove_rule(self, rule_id):
        try:
            self.alert_store.remove_rule(rule_id)
        except OSError as error:
            QMessageBox.critical(self, "Não foi possível remover", str(error))
            return
        self.refresh_rules()


class StockAlertsDialog(QDialog):
    def __init__(self, alerts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Produtos em atenção • Mix Moda")
        self.resize(900, 620)
        self.setMinimumSize(700, 440)
        self.setStyleSheet(PALETTE)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)

        eyebrow = QLabel("ACOMPANHAMENTO DE ESTOQUE")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)
        title = QLabel("Produtos em atenção")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel(
            "Estes produtos atingiram a faixa de estoque definida nas suas regras. "
            "A quantidade exibida corresponde à última análise."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        table = QTableWidget(len(alerts), 5)
        table.setHorizontalHeaderLabels(["Produto", "Código", "Loja", "Estoque atual", "Preço de venda"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        for row, alert in enumerate(alerts):
            values = [
                str(alert.get("descricao", "")),
                str(alert.get("codigo_barras", "")),
                str(alert.get("loja", "")),
                f"{br_number(alert.get('quantidade_estoque', 0), 0)} un.  (limite "
                f"{alert.get('estoque_minimo', 0)}–{alert.get('estoque_maximo', 0)})",
                brl(alert.get("preco_venda", 0)),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
            table.setRowHeight(row, 42)
        layout.addWidget(table, 1)
        root.addWidget(panel, 1)

        footer = QHBoxLayout()
        count = QLabel(f"{len(alerts)} produto(s) dentro da faixa configurada")
        count.setObjectName("muted")
        footer.addWidget(count, 1)
        close = QPushButton("FECHAR")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

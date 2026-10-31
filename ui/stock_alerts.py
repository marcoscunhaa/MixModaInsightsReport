"""UI to configure stock rules and review stock alerts."""
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, 
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from rapidfuzz import fuzz

from core.stock_alerts import StockAlertStore
from exports.stock_alerts_export import export_stock_alerts_xlsx
from core.stores import STORES
from utils.formatting import fmt_money, fmt_number
from utils.normalization import normalize_barcode, normalize_text
from ui.window_chrome import confirm_action, get_save_file, install_mac_window_chrome, show_message


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
QCheckBox { color:#233451; font-size:12px; font-weight:700; spacing:7px; }
QCheckBox:disabled { color:#A3AEC0; }
QCheckBox#allStores { color:#2854D9; font-weight:900; }
"""


RULES_QSS = """
QDialog { background:#F4F7FC; }
QLabel { background:transparent; color:#16233F; }
QFrame#hero { border-radius:22px;
    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #2F5BEA,stop:1 #7C3AED); }
QFrame#hero QLabel { color:#FFFFFF; }
QFrame#hero QLabel#heroIcon { background:rgba(255,255,255,0.18); border-radius:16px; font-size:26px; }
QFrame#hero QLabel#heroEyebrow { color:#DCE3FF; font-size:10px; font-weight:900; letter-spacing:1.5px; }
QFrame#hero QLabel#heroTitle { font-size:24px; font-weight:900; }
QFrame#hero QLabel#heroText { color:#E6EAFF; font-size:12px; }
QFrame#hero QFrame#heroStat { background:rgba(255,255,255,0.14); border:1px solid rgba(255,255,255,0.22); border-radius:16px; }
QFrame#hero QLabel#heroNumber { font-size:28px; font-weight:900; }
QFrame#hero QLabel#heroCaption { color:#DCE3FF; font-size:10px; font-weight:900; letter-spacing:1px; }
QFrame#card { background:#FFFFFF; border:1px solid #DCE6F3; border-radius:20px; }
QFrame#card QWidget { background:transparent; }
QFrame#card QLabel#cardTitle { color:#12213D; font-size:16px; font-weight:900; }
QFrame#card QLabel#stepNumber { background:#EEF2FF; color:#2F5BEA; border-radius:11px; font-size:11px; font-weight:900; }
QFrame#card QLabel#stepTitle { color:#12213D; font-size:12px; font-weight:900; letter-spacing:0.5px; }
QFrame#card QLabel#muted { color:#7A879D; font-size:11px; }
QFrame#card QLabel#hint { color:#7A879D; font-size:11px; padding:2px 2px; }
QFrame#card QLabel#countPill { background:#EEF2FF; color:#2F5BEA; border-radius:10px; padding:3px 10px; font-size:10px; font-weight:900; }
QFrame#card QLineEdit { background:#F8FAFD; border:1px solid #DCE4F0; border-radius:12px; padding:10px 12px; color:#233451; font-size:12px; }
QFrame#card QLineEdit:focus { border:1px solid #5675E8; background:#FFFFFF; }
QFrame#card QListWidget { background:#F8FAFD; border:1px solid #E2E8F1; border-radius:12px; padding:4px; outline:none; }
QFrame#card QListWidget::item { padding:8px 10px; border-radius:8px; color:#233451; margin:1px 0; }
QFrame#card QListWidget::item:hover { background:#EEF3FF; }
QFrame#card QListWidget::item:selected { background:#2F5BEA; color:#FFFFFF; }
QFrame#card QCheckBox { background:#F4F7FC; border:1px solid #DCE4F0; border-radius:14px; padding:7px 12px;
    color:#40516E; font-size:11px; font-weight:800; spacing:6px; }
QFrame#card QCheckBox:hover { border-color:#AFC2FF; }
QFrame#card QCheckBox:checked { background:#EEF3FF; border-color:#2F5BEA; color:#2F5BEA; }
QFrame#card QCheckBox:disabled { background:#F7F8FB; border-color:#E8EDF4; color:#A3AEC0; }
QFrame#card QCheckBox#allStores:checked { background:#2F5BEA; border-color:#2F5BEA; color:#FFFFFF; }
QFrame#card QLineEdit#minimumField { background:#F8FAFD; border:1px solid #DCE4F0; border-radius:12px; padding:0 6px;
    color:#12213D; font-size:16px; font-weight:900; min-height:0; }
QFrame#card QLineEdit#minimumField:focus { border:1px solid #5675E8; background:#FFFFFF; }
QLabel#footNote { color:#7A879D; font-size:11px; }
QFrame#card QPushButton#stepper { background:#EEF2FF; color:#2F5BEA; border:none; border-radius:12px; font-size:18px; font-weight:900;
    padding:0; min-width:40px; max-width:40px; min-height:40px; max-height:40px; }
QFrame#card QPushButton#stepper:hover { background:#DCE6FF; }
QFrame#card QPushButton#saveRule { border:none; border-radius:14px; padding:13px 18px; color:#FFFFFF; font-size:12px; font-weight:900;
    letter-spacing:0.5px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2F5BEA,stop:1 #7C3AED); }
QFrame#card QPushButton#saveRule:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2A51D6,stop:1 #6D2FE0); }
QFrame#card QPushButton#saveRule:disabled { background:#DCE3EF; color:#8C99AE; }
QFrame#card QTableWidget { background:#FFFFFF; border:none; gridline-color:transparent; outline:none; }
QFrame#card QTableWidget::item { border-bottom:1px solid #EEF2F7; padding:0 6px; }
QFrame#card QTableWidget::item:selected { background:#F5F8FF; color:#16233F; }
QFrame#card QHeaderView::section { background:#FFFFFF; color:#7A879D; border:none; border-bottom:1px solid #E3E9F2;
    padding:8px 6px; font-size:10px; font-weight:900; letter-spacing:1px; }
QFrame#card QLabel#ruleName { color:#12213D; font-size:12px; font-weight:800; }
QFrame#card QLabel#ruleCode { color:#8A96AA; font-size:10px; }
QFrame#card QLabel#storePill { background:#EEF3FF; color:#2F5BEA; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QFrame#card QLabel#storeAll { background:#F3EEFF; color:#7C3AED; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QFrame#card QLabel#limitPill { background:#FFF0F3; color:#D9284B; border-radius:10px; padding:4px 10px; font-size:10px; font-weight:900; }
QFrame#card QPushButton#iconEdit, QFrame#card QPushButton#iconDelete { border-radius:9px; font-size:13px; min-width:32px; max-width:32px;
    min-height:30px; max-height:30px; padding:0; }
QFrame#card QPushButton#iconEdit { background:#EEF3FF; border:1px solid #D5E0FF; }
QFrame#card QPushButton#iconEdit:hover { background:#DCE6FF; }
QFrame#card QPushButton#iconDelete { background:#FFF0F2; border:1px solid #FFD0D9; }
QFrame#card QPushButton#iconDelete:hover { background:#FFE0E5; }
QFrame#card QLabel#emptyRules { color:#8A96AA; font-size:12px; padding:30px; }
"""


class _IntField(QLineEdit):
    """Simple numeric field (digits only) with the QSpinBox interface used here.

    Replaces QSpinBox because the app-wide style hid the number inside it.
    """

    def __init__(self, value=0, minimum=0, maximum=100000, parent=None):
        super().__init__(parent)
        self._minimum, self._maximum = minimum, maximum
        self.setValidator(QIntValidator(minimum, maximum, self))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editingFinished.connect(lambda: self.setValue(self.value()))
        self.setValue(value)

    def value(self):
        try:
            number = int(self.text())
        except ValueError:
            number = self._minimum
        return max(self._minimum, min(self._maximum, number))

    def setValue(self, value):
        self.setText(str(max(self._minimum, min(self._maximum, int(value)))))

    def stepUp(self):
        self.setValue(self.value() + 1)

    def stepDown(self):
        self.setValue(self.value() - 1)


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
        self.editing_rule = None
        self.setWindowTitle("Stock rules • Mix Moda")
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = min(1050, available.width() - 32) if available else 1050
        height = min(820, available.height() - 48) if available else 820
        width, height = max(560, width), max(480, height)
        self.resize(width, height)
        self.setMinimumSize(min(760, width), min(540, height))
        self.setStyleSheet(RULES_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(14)
        install_mac_window_chrome(self, root)
        root.addWidget(self._heading())
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._editor(), 5)
        body.addWidget(self._rules_panel(), 7)
        root.addLayout(body, 1)
        root.addLayout(self._footer())

        self.refresh_rules()
        self.refresh_products("")

    @staticmethod
    def _card():
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    @staticmethod
    def _step(number, title):
        row = QHBoxLayout()
        row.setSpacing(8)
        badge = QLabel(str(number))
        badge.setObjectName("stepNumber")
        badge.setFixedSize(22, 22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(badge)
        label = QLabel(title)
        label.setObjectName("stepTitle")
        row.addWidget(label)
        row.addStretch()
        return row

    def _heading(self):
        hero = QFrame()
        hero.setObjectName("hero")
        row = QHBoxLayout(hero)
        row.setContentsMargins(24, 20, 24, 20)
        row.setSpacing(16)
        icon = QLabel("🔔")
        icon.setObjectName("heroIcon")
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        eyebrow = QLabel("SMART STOCK MANAGEMENT")
        eyebrow.setObjectName("heroEyebrow")
        texts.addWidget(eyebrow)
        title = QLabel("Critical stock rules")
        title.setObjectName("heroTitle")
        texts.addWidget(title)
        subtitle = QLabel("Pick the products that matter and decide when their stock should get your attention.")
        subtitle.setObjectName("heroText")
        subtitle.setWordWrap(True)
        texts.addWidget(subtitle)
        row.addLayout(texts, 1)
        stat = QFrame()
        stat.setObjectName("heroStat")
        stat_box = QVBoxLayout(stat)
        stat_box.setContentsMargins(20, 10, 20, 10)
        stat_box.setSpacing(0)
        self.hero_count = QLabel("0")
        self.hero_count.setObjectName("heroNumber")
        self.hero_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stat_box.addWidget(self.hero_count)
        self.hero_caption = QLabel("ACTIVE RULES")
        self.hero_caption.setObjectName("heroCaption")
        self.hero_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stat_box.addWidget(self.hero_caption)
        row.addWidget(stat, 0, Qt.AlignmentFlag.AlignVCenter)
        return hero

    def _editor(self):
        panel = self._card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        title = QLabel("✨  New rule")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        layout.addSpacing(4)

        layout.addLayout(self._step(1, "PRODUCT"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Search by product name or barcode")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_products)
        layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setMinimumHeight(110)
        self.results.setMaximumHeight(170)
        self.results.currentItemChanged.connect(self.select_product)
        layout.addWidget(self.results)
        self.selected_label = QLabel("Type at least 2 characters to find a product.")
        self.selected_label.setObjectName("hint")
        self.selected_label.setWordWrap(True)
        layout.addWidget(self.selected_label)

        layout.addSpacing(6)
        layout.addLayout(self._step(2, "STORES"))
        layout.addWidget(self._store_checkboxes())

        layout.addSpacing(6)
        layout.addLayout(self._step(3, "MINIMUM STOCK"))
        limit = QHBoxLayout()
        limit.setSpacing(8)
        minus = QPushButton("−")
        minus.setObjectName("stepper")
        minus.setFixedSize(40, 40)
        limit.addWidget(minus)
        self.minimum = _IntField(3, 0, 100000)
        self.minimum.setObjectName("minimumField")
        self.minimum.setFixedSize(90, 40)
        self.minimum.setToolTip("Alert when stock is at or below this limit.")
        limit.addWidget(self.minimum)
        plus = QPushButton("+")
        plus.setObjectName("stepper")
        plus.setFixedSize(40, 40)
        limit.addWidget(plus)
        minus.clicked.connect(lambda checked=False: self.minimum.stepDown())
        plus.clicked.connect(lambda checked=False: self.minimum.stepUp())
        unit = QLabel("units or fewer")
        unit.setObjectName("muted")
        limit.addWidget(unit)
        limit.addStretch()
        layout.addLayout(limit)

        layout.addStretch(1)
        self.status = QLabel("Alert when stock reaches this number of units or fewer.")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.save_button = QPushButton("＋  SAVE RULE")
        self.save_button.setObjectName("saveRule")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_rule)
        layout.addWidget(self.save_button)
        return panel

    def _set_hint(self, text, selected=False):
        self.selected_label.setText(text)
        self.selected_label.setStyleSheet(
            "background:#E8FAF5;color:#087F6A;border-radius:10px;padding:8px 10px;font-size:11px;font-weight:800;"
            if selected else ""
        )

    def _store_checkboxes(self):
        """"All stores" or specific stores; each checked store becomes one rule."""
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.all_stores = QCheckBox("All stores")
        self.all_stores.setObjectName("allStores")
        self.all_stores.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_stores.toggled.connect(self._toggle_all_stores)
        grid.addWidget(self.all_stores, 0, 0)
        self.store_checks = []
        for index, store in enumerate(STORES, start=1):
            check = QCheckBox(store)
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            self.store_checks.append((check, store))
            grid.addWidget(check, index // 3, index % 3)
        self.all_stores.setChecked(True)
        return box

    def _toggle_all_stores(self, checked):
        for check, _store in self.store_checks:
            check.setEnabled(not checked)

    def _set_selected_stores(self, store):
        self.all_stores.setChecked(store == "*")
        for check, name in self.store_checks:
            check.setChecked(store != "*" and normalize_text(name) == normalize_text(store))

    def _selected_stores(self):
        if self.all_stores.isChecked():
            return ["*"]
        return [name for check, name in self.store_checks if check.isChecked()]

    def _rules_panel(self):
        panel = self._card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        title = QLabel("📋  Your rules")
        title.setObjectName("cardTitle")
        heading.addWidget(title)
        heading.addStretch()
        self.rule_count = QLabel()
        self.rule_count.setObjectName("countPill")
        heading.addWidget(self.rule_count)
        layout.addLayout(heading)

        self.rules_table = QTableWidget(0, 4)
        self.rules_table.setHorizontalHeaderLabels(["PRODUCT", "STORE", "LIMIT", ""])
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.rules_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rules_table.setShowGrid(False)
        self.rules_table.verticalHeader().setVisible(False)
        header = self.rules_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.rules_table, 1)
        self.empty_rules = QLabel("🔕\n\nNo rules yet.\nCreate your first one on the left to track a product.")
        self.empty_rules.setObjectName("emptyRules")
        self.empty_rules.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_rules.hide()
        layout.addWidget(self.empty_rules, 1)
        return panel

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setObjectName("stepTitle")
        return label

    def _footer(self):
        row = QHBoxLayout()
        note = QLabel("🔒  Rules are saved on this computer and checked against the data from the latest analysis.")
        note.setObjectName("footNote")
        note.setWordWrap(True)
        row.addWidget(note, 1)
        return row

    def refresh_products(self, text):
        self.results.clear()
        self.selected_product = None
        self.save_button.setEnabled(False)
        query = str(text).strip()
        if len(query) < 2:
            self._set_hint("Type at least 2 characters to find a product.")
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
            description = str(product.get("descricao", "Product"))
            barcode = str(product.get("codigo_barras", ""))
            item = QListWidgetItem(f"{description}  •  {barcode}")
            item.setData(Qt.ItemDataRole.UserRole, (normalize_barcode(barcode), normalize_text(description)))
            self.results.addItem(item)
        if not matches:
            self._set_hint("No products found. Try another word or part of the barcode.")
        else:
            self._set_hint(f"{len(matches)} products found. Select one to set up the rule.")

    def select_product(self, current, _previous):
        self.selected_product = None
        self.save_button.setEnabled(False)
        if current is None:
            return
        self.selected_product = self.products_by_key.get(current.data(Qt.ItemDataRole.UserRole))
        if self.selected_product:
            self._set_hint(
                f"✓  {self.selected_product.get('descricao', '')}  •  "
                f"{self.selected_product.get('codigo_barras', '')}",
                selected=True,
            )
            self.save_button.setEnabled(True)

    def save_rule(self):
        if not self.selected_product:
            return
        stores = self._selected_stores()
        if not stores:
            show_message(self, "warning", "Choose the stores", "Check \"All stores\" or at least one store.")
            return
        minimum = self.minimum.value()
        product = self.selected_product
        key = (normalize_barcode(product.get("codigo_barras")), normalize_text(product.get("descricao")))
        try:
            for store in stores:
                self.alert_store.upsert_rule({
                    "codigo_barras": product.get("codigo_barras"),
                    "descricao": product.get("descricao"),
                    "loja": store,
                    "estoque_minimo": minimum,
                })
            # Editing a rule whose store was unchecked: the old rule is removed.
            rule = self.editing_rule
            if rule and key == (normalize_barcode(rule.get("codigo_barras")), normalize_text(rule.get("descricao"))):
                if normalize_text(rule.get("loja", "*")) not in {normalize_text(s) for s in stores}:
                    self.alert_store.remove_rule(rule.get("id"))
        except (OSError, ValueError) as error:
            show_message(self, "critical", "Could not save", str(error))
            return
        self.editing_rule = None
        where = "all stores" if stores == ["*"] else f"{len(stores)} store(s)"
        self.status.setText(f"Rule saved for {where}. The alert shows up when stock reaches the limit or drops below it.")
        self.refresh_rules()

    def refresh_rules(self):
        rules = self.alert_store.load_rules()
        count = len(rules)
        self.rule_count.setText(f"{count} RULE{'S' if count != 1 else ''}")
        self.hero_count.setText(str(count))
        self.hero_caption.setText("ACTIVE RULE" if count == 1 else "ACTIVE RULES")
        self.rules_table.setVisible(bool(rules))
        self.empty_rules.setVisible(not rules)
        self.rules_table.setRowCount(count)
        for row, rule in enumerate(rules):
            store = rule.get("loja", "*")
            # Keep the text on the items (search/accessibility); the visuals come from widgets.
            for col, value in enumerate((rule.get("descricao", ""), "All stores" if store == "*" else store,
                                         f"Up to {rule.get('estoque_minimo', 0)} units")):
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(0, 0, 0, 0))
                self.rules_table.setItem(row, col, item)

            product = QWidget()
            product_box = QVBoxLayout(product)
            product_box.setContentsMargins(6, 6, 6, 6)
            product_box.setSpacing(1)
            name = QLabel(str(rule.get("descricao", "")))
            name.setObjectName("ruleName")
            product_box.addWidget(name)
            code = QLabel(str(rule.get("codigo_barras", "")))
            code.setObjectName("ruleCode")
            product_box.addWidget(code)
            self.rules_table.setCellWidget(row, 0, product)

            store_label = QLabel("🏬  All stores" if store == "*" else store)
            store_label.setObjectName("storeAll" if store == "*" else "storePill")
            self.rules_table.setCellWidget(row, 1, self._centered(store_label))

            limit = QLabel(f"≤ {rule.get('estoque_minimo', 0)} units")
            limit.setObjectName("limitPill")
            self.rules_table.setCellWidget(row, 2, self._centered(limit))

            actions = QWidget()
            actions_box = QHBoxLayout(actions)
            actions_box.setContentsMargins(4, 0, 4, 0)
            actions_box.setSpacing(6)
            edit = QPushButton("✏️")
            edit.setObjectName("iconEdit")
            edit.setToolTip("Edit rule")
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.clicked.connect(lambda checked=False, saved=dict(rule): self.edit_rule(saved))
            actions_box.addWidget(edit)
            remove = QPushButton("🗑️")
            remove.setObjectName("iconDelete")
            remove.setToolTip("Delete rule")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.clicked.connect(lambda checked=False, rule_id=rule.get("id"): self.remove_rule(rule_id))
            actions_box.addWidget(remove)
            self.rules_table.setCellWidget(row, 3, actions)
            self.rules_table.setRowHeight(row, 56)

    @staticmethod
    def _centered(label):
        holder = QWidget()
        box = QHBoxLayout(holder)
        box.setContentsMargins(6, 0, 6, 0)
        box.addWidget(label)
        box.addStretch()
        return holder

    def edit_rule(self, rule):
        key = (
            normalize_barcode(rule.get("codigo_barras")),
            normalize_text(rule.get("descricao")),
        )
        product = self.products_by_key.get(key)
        if not product:
            show_message(
                self,
                "warning",
                "Product not found",
                "This product is not in the loaded catalog. Remove the rule or select another product.",
            )
            return

        description = str(product.get("descricao", ""))
        self.search.setText(str(product.get('codigo_barras', '')))
        for index in range(self.results.count()):
            item = self.results.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self.results.setCurrentItem(item)
                break
        self._set_selected_stores(rule.get("loja", "*"))
        self.editing_rule = dict(rule)
        self.minimum.setValue(int(rule.get("estoque_minimo", 0)))
        self.status.setText("Adjust the limit and save to update this rule.")
        self.search.setFocus()

    def remove_rule(self, rule_id):
        rule = next((item for item in self.alert_store.load_rules() if str(item.get("id")) == str(rule_id)), None)
        if not rule:
            self.refresh_rules()
            return
        confirmed = confirm_action(
            self,
            "Delete stock rule",
            f"Delete the rule for “{rule.get('descricao', 'product')}” in "
            f"{'all stores' if rule.get('loja', '*') == '*' else rule.get('loja')}?",
            "Delete rule",
        )
        if not confirmed:
            return
        try:
            self.alert_store.remove_rule(rule_id)
        except OSError as error:
            show_message(self, "critical", "Could not remove", str(error))
            return
        self.status.setText("Rule removed.")
        self.refresh_rules()


class StockAlertsDialog(QDialog):
    def __init__(self, alerts, parent=None):
        super().__init__(parent)
        self.alerts = list(alerts)
        self.setWindowTitle("Products needing attention • Mix Moda")
        self.resize(900, 620)
        self.setMinimumSize(700, 440)
        self.setStyleSheet(PALETTE)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(12)
        install_mac_window_chrome(self, root)

        eyebrow = QLabel("STOCK MONITORING")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)
        title = QLabel("Products needing attention")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel(
            "These products reached the stock level set in your rules. "
            "The quantity shown comes from the latest analysis."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        table = QTableWidget(len(alerts), 5)
        table.setHorizontalHeaderLabels(["Product", "Barcode", "Store", "Current stock", "Sale price"])
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
                f"{fmt_number(alert.get('quantidade_estoque', 0), 0)} units  (limit ≤ "
                f"{alert.get('estoque_minimo', 0)})",
                fmt_money(alert.get("preco_venda", 0)),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(value))
            table.setRowHeight(row, 42)
        layout.addWidget(table, 1)
        if not alerts:
            table.hide()
            empty = QLabel("All good")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#16836D;font-size:18px;font-weight:900;padding:28px;")
            detail = QLabel("No product reached the stock level set in your rules.")
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail.setWordWrap(True)
            detail.setStyleSheet("color:#74829A;font-size:11px;padding:0 20px 24px;")
            layout.addWidget(empty)
            layout.addWidget(detail)
        root.addWidget(panel, 1)

        footer = QHBoxLayout()
        count = QLabel(f"{len(alerts)} product(s) within the configured range")
        count.setObjectName("muted")
        footer.addWidget(count, 1)
        export_button = QPushButton("EXPORT TO EXCEL")
        export_button.setEnabled(bool(self.alerts))
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setStyleSheet(
            "QPushButton{background:#16836D;color:white;border:0;border-radius:10px;"
            "padding:9px 15px;font-weight:900;}"
            "QPushButton:hover{background:#106B59;}"
            "QPushButton:disabled{background:#D8E0E9;color:#8793A5;}"
        )
        export_button.clicked.connect(self.export_excel)
        footer.addWidget(export_button)
        close = QPushButton("CLOSE")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    def export_excel(self):
        path = get_save_file(
            self,
            "Export alerts to Excel",
            "MixModa_Restock_List.xlsx",
            "Excel (*.xlsx)",
            "xlsx",
        )
        if not path:
            return
        try:
            export_stock_alerts_xlsx(path, self.alerts)
        except (OSError, ValueError, ImportError) as error:
            show_message(self, "critical", "Export failed", str(error))
            return
        show_message(
            self,
            "information",
            "Spreadsheet exported",
            f"File saved successfully to:\n{path}",
        )

"""Explore stock: Group → Subclass → Product, with create, edit and delete.

The cards share the look of the dashboard explorer. Data comes straight from the
catalog JSON (no generated analysis needed) and every change is written to the
file immediately through core.catalog_editor.
"""
import copy

from PySide6.QtCore import QRegularExpression, QSize, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QCheckBox, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from core import catalog_editor as ce
from core.stores import STORES
from ui.explorer_cards import ExplorerCard, _stable_color
from ui.window_chrome import confirm_action, install_mac_window_chrome, show_message
from utils.formatting import fmt_number
from utils.normalization import normalize_barcode, normalize_text

SEARCH_LIMIT = 300

EDITOR_QSS = """
QDialog { background:#F3F6FB; }
QLabel#eyebrow { color:#526FE3; font-size:10px; font-weight:900; letter-spacing:1px; }
QLabel#title { color:#14284B; font-size:22px; font-weight:900; }
QLabel#section { color:#192D50; font-size:13px; font-weight:900; }
QLabel#muted { color:#74829A; font-size:11px; }
QFrame#panel { background:#FFFFFF; border:1px solid #E0E7F1; border-radius:16px; }
QLineEdit, QComboBox { background:#F8FAFD; border:1px solid #DCE4F0;
    border-radius:9px; padding:7px 9px; color:#233451; }
QLineEdit:focus, QComboBox:focus { border:1px solid #5675E8; background:#FFFFFF; }
QCheckBox { color:#233451; font-size:12px; font-weight:700; spacing:7px; }
"""


def _uppercase_as_typed(line_edit):
    """Upper-case typed text without touching what the program filled in."""
    def apply(text):
        upper = text.upper()
        if upper != text:
            pos = line_edit.cursorPosition()
            line_edit.setText(upper)
            line_edit.setCursorPosition(pos)
    line_edit.textEdited.connect(apply)


def _matches(product, query):
    text = normalize_text(f"{product.get('codigo_barras', '')} {product.get('descricao', '')}")
    code = normalize_barcode(query)
    return all(word in text for word in query.split()) or (
        code not in ("", "0") and code in normalize_barcode(product.get("codigo_barras"))
    )


class StockExplorerPage(QWidget):
    """Home-menu page. `catalog` is the same dict used by the rest of the app."""

    def __init__(self, catalog, catalog_path, on_home=None, on_catalog_changed=None, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.catalog_path = catalog_path
        self.on_home = on_home or (lambda: None)
        self.on_catalog_changed = on_catalog_changed or (lambda: None)
        self.path = []

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 26)
        root.setSpacing(12)

        head = QHBoxLayout()
        titlebox = QVBoxLayout()
        self.title = QLabel("Stock • Groups")
        self.title.setStyleSheet("font-size:24px;font-weight:900;color:#12213D;")
        titlebox.addWidget(self.title)
        self.crumb = QLabel("")
        self.crumb.setStyleSheet("color:#64728A;font-size:12px;font-weight:800;")
        titlebox.addWidget(self.crumb)
        head.addLayout(titlebox)
        head.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by description or barcode...")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(300)
        self.search.textChanged.connect(lambda _text: self.render())
        head.addWidget(self.search)
        new_button = QPushButton("＋  NEW PRODUCT")
        new_button.setObjectName("AddStore")
        new_button.clicked.connect(self.new_product)
        head.addWidget(new_button)
        self.back = QPushButton("← Back")
        self.back.setObjectName("Ghost")
        self.back.clicked.connect(self.go_back)
        head.addWidget(self.back)
        root.addLayout(head)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSpacing(10)
        self.list.setGridSize(QSize(350, 116))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.itemClicked.connect(self.open_item)
        root.addWidget(self.list, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        root.addWidget(self.empty)
        self.render()

    # ---------- navigation ----------
    def products(self):
        return self.catalog.get("produtos", [])

    def reset(self):
        self.path = []
        self.search.clear()
        self.render()

    def render(self):
        self.list.clear()
        query = normalize_text(self.search.text())
        if query:
            self.render_search(query)
        elif len(self.path) == 2:
            self.render_products(*self.path)
        elif len(self.path) == 1:
            self.render_subclasses(self.path[0])
        else:
            self.render_groups()
        self.empty.setVisible(self.list.count() == 0)

    def _add_card(self, title, subtitle, value, kind, key, accent):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, (kind, key))
        item.setSizeHint(QSize(340, 104))
        self.list.addItem(item)
        self.list.setItemWidget(item, ExplorerCard("", title, subtitle, value, accent, flat=True))

    def _summary(self, items, second):
        # No quantities: real stock comes from the spreadsheet imported in the analysis.
        inactive = sum(1 for p in items if p.get("situacao") != ce.ACTIVE)
        subtitle = f"{fmt_number(len(items), 0)} products"
        if inactive:
            subtitle += f"  •  {fmt_number(inactive, 0)} inactive"
        return subtitle, second

    def render_groups(self):
        self.title.setText("Stock • Groups")
        self.crumb.setText("All groups")
        self.back.setText("← Home")
        groups = {}
        for product in self.products():
            groups.setdefault(product.get("grupo", ""), []).append(product)
        for name in sorted(groups, key=normalize_text):
            subs = len({p.get("subclasse") for p in groups[name]})
            subtitle, value = self._summary(groups[name], f"{fmt_number(subs, 0)} subclasses")
            self._add_card(name or "NO GROUP", subtitle, value, "group", name, _stable_color(name))
        self.empty.setText("No products registered.")

    def render_subclasses(self, group):
        self.title.setText(f"{group} • Subclasses")
        self.crumb.setText(f"All groups  ›  {group}")
        self.back.setText("← Back")
        subs = {}
        for product in self.products():
            if product.get("grupo") == group:
                subs.setdefault(product.get("subclasse", ""), []).append(product)
        for name in sorted(subs, key=normalize_text):
            stores = len({normalize_text(l.get("loja")) for p in subs[name] for l in p.get("lojas", [])})
            subtitle, value = self._summary(subs[name], f"in {fmt_number(stores, 0)} store{'s' if stores != 1 else ''}")
            self._add_card(name or "NO SUBCLASS", subtitle, value, "sub", name, _stable_color(name))
        self.empty.setText("No subclasses in this group.")

    def _add_product_card(self, product):
        subtitle = str(product.get("codigo_barras", ""))
        if product.get("situacao") != ce.ACTIVE:
            subtitle += f"  •  {product.get('situacao', '')}"
        value = ", ".join(l.get("loja", "") for l in product.get("lojas", [])) or "No store"
        self._add_card(product.get("descricao", ""), subtitle, value, "product",
                       product.get("codigo_barras"), _stable_color(product.get("descricao", "")))

    def render_products(self, group, sub):
        self.title.setText(f"Products • {sub}")
        self.crumb.setText(f"All groups  ›  {group}  ›  {sub}")
        self.back.setText("← Back")
        items = [p for p in self.products() if p.get("grupo") == group and p.get("subclasse") == sub]
        for product in sorted(items, key=lambda p: (normalize_text(p.get("descricao")), p.get("codigo_barras"))):
            self._add_product_card(product)
        self.empty.setText("No products in this subclass.")

    def render_search(self, query):
        found = [p for p in self.products() if _matches(p, query)]
        found.sort(key=lambda p: (normalize_text(p.get("descricao")), p.get("codigo_barras")))
        self.title.setText("Stock • Search")
        shown = found[:SEARCH_LIMIT]
        extra = f" (showing {SEARCH_LIMIT})" if len(found) > SEARCH_LIMIT else ""
        self.crumb.setText(f"{fmt_number(len(found), 0)} product(s) found{extra}")
        self.back.setText("← Clear search")
        for product in shown:
            self._add_product_card(product)
        self.empty.setText("No products found.")

    def open_item(self, item):
        kind, key = item.data(Qt.ItemDataRole.UserRole)
        if kind == "group":
            self.path = [key]
            self.render()
        elif kind == "sub":
            self.path = [self.path[0], key]
            self.render()
        elif kind == "product":
            product = ce.find_product(self.catalog, key)
            if product is not None:
                self.open_editor(product)

    def go_back(self):
        if self.search.text():
            self.search.clear()
        elif self.path:
            self.path = self.path[:-1]
            self.render()
        else:
            self.on_home()

    # ---------- CRUD ----------
    def new_product(self):
        defaults = {}
        if self.path:
            defaults["grupo"] = self.path[0]
        if len(self.path) == 2:
            defaults["subclasse"] = self.path[1]
        self.open_editor(None, defaults)

    def open_editor(self, product, defaults=None):
        dialog = ProductEditorDialog(self.catalog, product, self.commit, defaults, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_product is not None:
            # After saving, show the product where it ended up (it may have changed group).
            saved = dialog.result_product
            if not self.search.text():
                self.path = [saved["grupo"], saved["subclasse"]]
        self._fix_path()
        self.render()

    def _fix_path(self):
        groups = {p.get("grupo") for p in self.products()}
        if self.path and self.path[0] not in groups:
            self.path = []
        if len(self.path) == 2 and not any(
            p.get("grupo") == self.path[0] and p.get("subclasse") == self.path[1] for p in self.products()
        ):
            self.path = self.path[:1]

    def commit(self, change):
        """Apply `change` to a copy, write the file and only then update memory.

        If writing fails, the catalog in use stays exactly as it was.
        """
        candidate = copy.deepcopy(self.catalog)
        result = change(candidate)
        ce.save_catalog(candidate, self.catalog_path)
        self.catalog.clear()
        self.catalog.update(candidate)
        self.on_catalog_changed()
        if isinstance(result, dict):
            return ce.find_product(self.catalog, result["codigo_barras"])
        return result


class ProductEditorDialog(QDialog):
    """Create/edit form. `commit` saves; errors keep the form open."""

    def __init__(self, catalog, product, commit, defaults=None, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.product = product
        self.commit = commit
        self.result_product = None
        self.store_options = ce.store_names(catalog)
        self.tree = ce.groups_and_subclasses(catalog)
        data = copy.deepcopy(product) if product else {
            "codigo_barras": "", "descricao": "", "situacao": ce.ACTIVE,
            "grupo": "", "subclasse": "", "lojas": [], **(defaults or {}),
        }
        self.existing_stores = {normalize_text(l["loja"]): l for l in data.get("lojas", [])}

        self.setWindowTitle("Edit product" if product else "New product")
        self.setModal(True)
        self.resize(760, 520)
        self.setMinimumSize(640, 460)
        self.setStyleSheet(EDITOR_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(12)
        install_mac_window_chrome(self, root)

        eyebrow = QLabel("STOCK CATALOG")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)
        title = QLabel(data["descricao"] if product else "Add a new product")
        title.setObjectName("title")
        title.setWordWrap(True)
        root.addWidget(title)

        root.addWidget(self._general_panel(data))
        root.addWidget(self._stores_panel())
        root.addStretch(1)
        root.addLayout(self._footer())

    # ---------- layout ----------
    def _general_panel(self, data):
        panel = QFrame()
        panel.setObjectName("panel")
        form = QFormLayout(panel)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.code = QLineEdit(str(data.get("codigo_barras", "")))
        self.code.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,20}"), self.code))
        self.code.setPlaceholderText("Numbers only")
        form.addRow("Barcode", self.code)

        self.description = QLineEdit(data.get("descricao", ""))
        self.description.setPlaceholderText("E.g. PRINTED BABY TEE")
        _uppercase_as_typed(self.description)
        form.addRow("Description", self.description)

        self.group = self._editable_combo(list(self.tree), data.get("grupo", ""))
        self.group.currentTextChanged.connect(self._refresh_subclasses)
        form.addRow("Group", self.group)

        self.subclass = self._editable_combo([], "")
        self._refresh_subclasses(self.group.currentText())
        self.subclass.setEditText(data.get("subclasse", ""))
        form.addRow("Subclass", self.subclass)

        self.situation = QComboBox()
        self.situation.addItems(list(ce.SITUACOES))
        self.situation.setCurrentText(data.get("situacao") or ce.ACTIVE)
        form.addRow("Status", self.situation)
        return panel

    def _editable_combo(self, items, text):
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.addItems(items)
        combo.setEditText(text)
        combo.lineEdit().setPlaceholderText("Pick one or type a new one")
        _uppercase_as_typed(combo.lineEdit())
        return combo

    def _refresh_subclasses(self, group):
        current = self.subclass.currentText()
        self.subclass.blockSignals(True)
        self.subclass.clear()
        self.subclass.addItems(self.tree.get(group, []))
        self.subclass.setEditText(current)
        self.subclass.blockSignals(False)

    def _stores_panel(self):
        """Which stores carry the product. Quantity and price live in the spreadsheets."""
        panel = QFrame()
        panel.setObjectName("panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(18, 14, 18, 16)
        box.setSpacing(10)
        title = QLabel("STORES")
        title.setObjectName("section")
        box.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.store_checks = []
        official = {normalize_text(s): s for s in STORES}
        for name in self.store_options:
            # Show the official name ("Pedras"); save the catalog spelling ("pedras").
            check = QCheckBox(official.get(normalize_text(name), name))
            check.setChecked(normalize_text(name) in self.existing_stores)
            self.store_checks.append((check, name))
            row.addWidget(check)
        row.addStretch()
        box.addLayout(row)
        return panel

    def _footer(self):
        actions = QHBoxLayout()
        if self.product is not None:
            delete = QPushButton("Delete product")
            delete.setObjectName("Danger")
            delete.clicked.connect(lambda checked=False: self.delete())
            actions.addWidget(delete)
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(lambda checked=False: self.reject())
        actions.addWidget(cancel)
        save = QPushButton("Save changes" if self.product is not None else "Add product")
        save.clicked.connect(lambda checked=False: self.save())
        actions.addWidget(save)
        return actions

    def _selected_stores(self):
        """Checked stores. Existing ones keep their description, quantity and price."""
        stores = []
        for check, name in self.store_checks:
            if not check.isChecked():
                continue
            previous = self.existing_stores.get(normalize_text(name))
            if previous is not None:
                stores.append({
                    "loja": previous["loja"],
                    "descricao": previous.get("descricao", ""),
                    "quantidade_catalogo": previous.get("quantidade_catalogo", 0),
                    "valor": previous.get("valor", 0),
                })
            else:
                stores.append({"loja": name, "descricao": "", "quantidade_catalogo": 0, "valor": 0})
        return stores

    # ---------- actions ----------
    def form_data(self):
        return {
            "codigo_barras": self.code.text(),
            "descricao": self.description.text(),
            "grupo": self.group.currentText(),
            "subclasse": self.subclass.currentText(),
            "situacao": self.situation.currentText(),
            "lojas": self._selected_stores(),
        }

    def save(self):
        data = self.form_data()
        original = self.product["codigo_barras"] if self.product else None
        try:
            if original is None:
                saved = self.commit(lambda catalog: ce.add_product(catalog, data))
            else:
                saved = self.commit(lambda catalog: ce.update_product(catalog, original, data))
        except ce.CatalogValidationError as error:
            show_message(self, "warning", "Check the data", str(error))
            return
        except OSError as error:
            show_message(self, "critical", "Could not save",
                         f"The catalog could not be written.\n\n{error}")
            return
        self.result_product = saved
        self.accept()

    def delete(self):
        name = self.product.get("descricao", "")
        code = self.product.get("codigo_barras", "")
        if not confirm_action(
            self, "Delete product",
            f"Delete {name} ({code}) from the catalog?\n\n"
            "The product is removed from every store. A copy of the previous file is saved as .bak.",
        ):
            return
        try:
            self.commit(lambda catalog: ce.delete_product(catalog, code))
        except (ce.CatalogValidationError, OSError) as error:
            show_message(self, "critical", "Could not delete", str(error))
            return
        self.result_product = None
        self.accept()

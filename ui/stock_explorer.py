"""Explorar estoque: Grupo → Subclasse → Produto, com cadastro, edição e exclusão.

Os cards seguem o mesmo visual do explorador do dashboard. Os dados vêm direto do
catálogo JSON (não dependem de uma análise gerada) e cada alteração é gravada no
arquivo na hora, através de core.catalog_editor.
"""
import copy

from PySide6.QtCore import QRegularExpression, QSize, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
    QTableWidget, QVBoxLayout, QWidget,
)

from core import catalog_editor as ce
from ui.dashboard_page import ExplorerCard, _stable_color
from ui.window_chrome import confirm_action, install_mac_window_chrome, show_message
from utils.formatting import brl, br_number
from utils.normalization import normalize_barcode, normalize_text

SEARCH_LIMIT = 300

EDITOR_QSS = """
QDialog { background:#F3F6FB; }
QLabel#eyebrow { color:#526FE3; font-size:10px; font-weight:900; letter-spacing:1px; }
QLabel#title { color:#14284B; font-size:22px; font-weight:900; }
QLabel#section { color:#192D50; font-size:13px; font-weight:900; }
QLabel#muted { color:#74829A; font-size:11px; }
QFrame#panel { background:#FFFFFF; border:1px solid #E0E7F1; border-radius:16px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#F8FAFD; border:1px solid #DCE4F0;
    border-radius:9px; padding:7px 9px; color:#233451; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border:1px solid #5675E8; background:#FFFFFF; }
QTableWidget { background:#FFFFFF; border:1px solid #E2E8F1; border-radius:10px; }
QTableWidget QLineEdit, QTableWidget QComboBox, QTableWidget QSpinBox, QTableWidget QDoubleSpinBox {
    border-radius:6px; padding:4px 6px; }
QPushButton#removeStore { background:#FFF0F2; color:#D9284B; border:1px solid #FFD0D9; border-radius:8px;
    padding:4px 10px; font-weight:900; }
QPushButton#removeStore:hover { background:#FFE1E6; }
"""


def _uppercase_as_typed(line_edit):
    """Deixa o texto digitado em caixa alta sem mexer no que foi preenchido pelo programa."""
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
    """Página do menu inicial. `catalog` é o mesmo dicionário usado pelo resto do app."""

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
        self.title = QLabel("Estoque • Grupos")
        self.title.setStyleSheet("font-size:24px;font-weight:900;color:#12213D;")
        titlebox.addWidget(self.title)
        self.crumb = QLabel("")
        self.crumb.setStyleSheet("color:#64728A;font-size:12px;font-weight:800;")
        titlebox.addWidget(self.crumb)
        head.addLayout(titlebox)
        head.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por descrição ou código...")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(300)
        self.search.textChanged.connect(lambda _text: self.render())
        head.addWidget(self.search)
        new_button = QPushButton("＋  NOVO PRODUTO")
        new_button.setObjectName("AddStore")
        new_button.clicked.connect(self.new_product)
        head.addWidget(new_button)
        self.back = QPushButton("← Voltar")
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

    # ---------- navegação ----------
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

    def _summary(self, items):
        stock = sum(ce.product_stock(p) for p in items)
        return f"{br_number(len(items), 0)} produtos", f"{br_number(stock, 0)} un. em estoque"

    def render_groups(self):
        self.title.setText("Estoque • Grupos")
        self.crumb.setText("Todos os grupos")
        self.back.setText("← Início")
        groups = {}
        for product in self.products():
            groups.setdefault(product.get("grupo", ""), []).append(product)
        for name in sorted(groups, key=normalize_text):
            subtitle, value = self._summary(groups[name])
            self._add_card(name or "SEM GRUPO", subtitle, value, "group", name, _stable_color(name))
        self.empty.setText("Nenhum produto cadastrado.")

    def render_subclasses(self, group):
        self.title.setText(f"{group} • Subclasses")
        self.crumb.setText(f"Todos os grupos  ›  {group}")
        self.back.setText("← Voltar")
        subs = {}
        for product in self.products():
            if product.get("grupo") == group:
                subs.setdefault(product.get("subclasse", ""), []).append(product)
        for name in sorted(subs, key=normalize_text):
            subtitle, value = self._summary(subs[name])
            self._add_card(name or "SEM SUBCLASSE", subtitle, value, "sub", name, _stable_color(name))
        self.empty.setText("Nenhuma subclasse neste grupo.")

    def _add_product_card(self, product):
        stores = product.get("lojas", [])
        subtitle = f"{product.get('codigo_barras', '')}  •  {len(stores)} loja{'s' if len(stores) != 1 else ''}"
        if product.get("situacao") != "ATIVO":
            subtitle += f"  •  {product.get('situacao', '')}"
        prices = [ce.parse_number(s.get("valor")) for s in stores]
        value = f"{br_number(ce.product_stock(product), 0)} un.  •  {brl(max(prices) if prices else 0)}"
        self._add_card(product.get("descricao", ""), subtitle, value, "product",
                       product.get("codigo_barras"), _stable_color(product.get("descricao", "")))

    def render_products(self, group, sub):
        self.title.setText(f"Produtos • {sub}")
        self.crumb.setText(f"Todos os grupos  ›  {group}  ›  {sub}")
        self.back.setText("← Voltar")
        items = [p for p in self.products() if p.get("grupo") == group and p.get("subclasse") == sub]
        for product in sorted(items, key=lambda p: (normalize_text(p.get("descricao")), p.get("codigo_barras"))):
            self._add_product_card(product)
        self.empty.setText("Nenhum produto nesta subclasse.")

    def render_search(self, query):
        found = [p for p in self.products() if _matches(p, query)]
        found.sort(key=lambda p: (normalize_text(p.get("descricao")), p.get("codigo_barras")))
        self.title.setText("Estoque • Busca")
        shown = found[:SEARCH_LIMIT]
        extra = f" (mostrando {SEARCH_LIMIT})" if len(found) > SEARCH_LIMIT else ""
        self.crumb.setText(f"{br_number(len(found), 0)} produto(s) encontrados{extra}")
        self.back.setText("← Limpar busca")
        for product in shown:
            self._add_product_card(product)
        self.empty.setText("Nenhum produto encontrado.")

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
            # Depois de salvar, mostra o produto onde ele ficou (pode ter mudado de grupo).
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
        """Aplica `change` numa cópia, grava o arquivo e só então atualiza a memória.

        Se a gravação falhar, o catálogo em uso continua exatamente como estava.
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
    """Formulário de cadastro/edição. `commit` grava; erros mantêm o formulário aberto."""

    def __init__(self, catalog, product, commit, defaults=None, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.product = product
        self.commit = commit
        self.result_product = None
        self.store_options = ce.store_names(catalog)
        self.tree = ce.groups_and_subclasses(catalog)
        data = copy.deepcopy(product) if product else {
            "codigo_barras": "", "descricao": "", "situacao": "ATIVO",
            "grupo": "", "subclasse": "", "lojas": [], **(defaults or {}),
        }
        self._last_description = data.get("descricao", "")

        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setModal(True)
        self.resize(900, 680)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(EDITOR_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(12)
        install_mac_window_chrome(self, root)

        eyebrow = QLabel("CATÁLOGO DE ESTOQUE")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)
        title = QLabel(data["descricao"] if product else "Cadastrar novo produto")
        title.setObjectName("title")
        title.setWordWrap(True)
        root.addWidget(title)

        root.addWidget(self._general_panel(data))
        root.addWidget(self._stores_panel(data), 1)
        root.addLayout(self._footer())

    # ---------- montagem ----------
    def _general_panel(self, data):
        panel = QFrame()
        panel.setObjectName("panel")
        form = QFormLayout(panel)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.code = QLineEdit(str(data.get("codigo_barras", "")))
        self.code.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,20}"), self.code))
        self.code.setPlaceholderText("Somente números")
        form.addRow("Código de barras", self.code)

        self.description = QLineEdit(data.get("descricao", ""))
        self.description.setPlaceholderText("Ex.: BLUSA BABY LOOK ESTAMPADA")
        _uppercase_as_typed(self.description)
        self.description.textEdited.connect(self._sync_store_descriptions)
        form.addRow("Descrição", self.description)

        self.group = self._editable_combo(list(self.tree), data.get("grupo", ""))
        self.group.currentTextChanged.connect(self._refresh_subclasses)
        form.addRow("Grupo", self.group)

        self.subclass = self._editable_combo([], "")
        self._refresh_subclasses(self.group.currentText())
        self.subclass.setEditText(data.get("subclasse", ""))
        form.addRow("Subclasse", self.subclass)

        self.situation = QComboBox()
        self.situation.addItems(list(ce.SITUACOES))
        self.situation.setCurrentText(data.get("situacao") or "ATIVO")
        form.addRow("Situação", self.situation)
        return panel

    def _editable_combo(self, items, text):
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.addItems(items)
        combo.setEditText(text)
        combo.lineEdit().setPlaceholderText("Escolha ou digite um novo")
        _uppercase_as_typed(combo.lineEdit())
        return combo

    def _refresh_subclasses(self, group):
        current = self.subclass.currentText()
        self.subclass.blockSignals(True)
        self.subclass.clear()
        self.subclass.addItems(self.tree.get(group, []))
        self.subclass.setEditText(current)
        self.subclass.blockSignals(False)

    def _stores_panel(self, data):
        panel = QFrame()
        panel.setObjectName("panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(18, 14, 18, 16)
        box.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("ESTOQUE POR LOJA")
        title.setObjectName("section")
        head.addWidget(title)
        head.addStretch()
        add = QPushButton("＋  Adicionar loja")
        add.setObjectName("Secondary")
        add.clicked.connect(lambda checked=False: self.add_store_row())
        head.addWidget(add)
        box.addLayout(head)
        hint = QLabel("A descrição da loja é a usada no cruzamento com as vendas daquela loja.")
        hint.setObjectName("muted")
        box.addWidget(hint)

        self.stores = QTableWidget(0, 5)
        self.stores.setHorizontalHeaderLabels(["Loja", "Descrição na loja", "Quantidade", "Valor", ""])
        self.stores.verticalHeader().setVisible(False)
        self.stores.verticalHeader().setDefaultSectionSize(46)
        self.stores.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.stores.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.stores.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        box.addWidget(self.stores, 1)
        for entry in data.get("lojas", []):
            self.add_store_row(entry)
        if not data.get("lojas"):
            self.add_store_row()
        return panel

    def _footer(self):
        actions = QHBoxLayout()
        if self.product is not None:
            delete = QPushButton("Excluir produto")
            delete.setObjectName("Danger")
            delete.clicked.connect(lambda checked=False: self.delete())
            actions.addWidget(delete)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(lambda checked=False: self.reject())
        actions.addWidget(cancel)
        save = QPushButton("Salvar alterações" if self.product is not None else "Cadastrar produto")
        save.clicked.connect(lambda checked=False: self.save())
        actions.addWidget(save)
        return actions

    # ---------- linhas de loja ----------
    def _used_stores(self):
        return {
            normalize_text(self.stores.cellWidget(r, 0).currentText())
            for r in range(self.stores.rowCount())
        }

    def add_store_row(self, entry=None):
        if entry is None:
            used = self._used_stores()
            free = [s for s in self.store_options if normalize_text(s) not in used]
            if not free:
                show_message(self, "information", "Todas as lojas adicionadas",
                             "Este produto já está em todas as lojas cadastradas.")
                return
            prices = [self.stores.cellWidget(r, 3).value() for r in range(self.stores.rowCount())]
            entry = {"loja": free[0], "descricao": self.description.text(),
                     "quantidade_catalogo": 0, "valor": prices[0] if prices else 0}

        row = self.stores.rowCount()
        self.stores.insertRow(row)
        store = QComboBox()
        options = list(self.store_options)
        if entry["loja"] and normalize_text(entry["loja"]) not in {normalize_text(s) for s in options}:
            options.append(entry["loja"])
        store.addItems(options)
        store.setCurrentText(entry["loja"])
        self.stores.setCellWidget(row, 0, store)

        description = QLineEdit(entry.get("descricao", ""))
        _uppercase_as_typed(description)
        self.stores.setCellWidget(row, 1, description)

        quantity = QSpinBox()
        quantity.setRange(-999999, 999999)  # o estoque real tem saldos negativos
        quantity.setValue(int(round(ce.parse_number(entry.get("quantidade_catalogo")))))
        quantity.setMinimumWidth(96)
        self.stores.setCellWidget(row, 2, quantity)

        price = QDoubleSpinBox()
        price.setRange(0, 999999.99)
        price.setDecimals(2)
        price.setPrefix("R$ ")
        price.setValue(ce.parse_number(entry.get("valor")))
        price.setMinimumWidth(120)
        self.stores.setCellWidget(row, 3, price)

        remove = QPushButton("✕")
        remove.setObjectName("removeStore")
        remove.setToolTip("Remover o produto desta loja")
        remove.clicked.connect(lambda checked=False, button=remove: self._remove_row(button))
        self.stores.setCellWidget(row, 4, remove)

    def _remove_row(self, button):
        for row in range(self.stores.rowCount()):
            if self.stores.cellWidget(row, 4) is button:
                self.stores.removeRow(row)
                return

    def _sync_store_descriptions(self, text):
        """Lojas que usavam a descrição geral acompanham a nova descrição."""
        old = normalize_text(self._last_description)
        for row in range(self.stores.rowCount()):
            field = self.stores.cellWidget(row, 1)
            if normalize_text(field.text()) == old:
                field.setText(text.upper())
        self._last_description = text.upper()

    # ---------- ações ----------
    def form_data(self):
        return {
            "codigo_barras": self.code.text(),
            "descricao": self.description.text(),
            "grupo": self.group.currentText(),
            "subclasse": self.subclass.currentText(),
            "situacao": self.situation.currentText(),
            "lojas": [
                {
                    "loja": self.stores.cellWidget(r, 0).currentText(),
                    "descricao": self.stores.cellWidget(r, 1).text(),
                    "quantidade_catalogo": self.stores.cellWidget(r, 2).value(),
                    "valor": self.stores.cellWidget(r, 3).value(),
                }
                for r in range(self.stores.rowCount())
            ],
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
            show_message(self, "warning", "Confira os dados", str(error))
            return
        except OSError as error:
            show_message(self, "critical", "Não foi possível salvar",
                         f"O catálogo não pôde ser gravado.\n\n{error}")
            return
        self.result_product = saved
        self.accept()

    def delete(self):
        name = self.product.get("descricao", "")
        code = self.product.get("codigo_barras", "")
        if not confirm_action(
            self, "Excluir produto",
            f"Excluir {name} ({code}) do catálogo?\n\n"
            "O produto sai de todas as lojas. Uma cópia do arquivo anterior fica salva como .bak.",
        ):
            return
        try:
            self.commit(lambda catalog: ce.delete_product(catalog, code))
        except (ce.CatalogValidationError, OSError) as error:
            show_message(self, "critical", "Não foi possível excluir", str(error))
            return
        self.result_product = None
        self.accept()

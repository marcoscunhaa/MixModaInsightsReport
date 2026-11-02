"""Selecionar vários produtos e ver todos juntos, por loja.

Pedido da loja: na busca por nome, poder marcar os itens que interessam (como
grifar no Excel) e abrir todos de uma vez, por exemplo os tamanhos de um
conjunto. A lista vem do menor código para o maior, então a grade fica em
sequência (P → GG), e as marcações continuam valendo ao mudar a busca.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from core.analyzer import match_options, product_options
from ui.copyable import install_copy_shortcut
from ui.window_chrome import install_mac_window_chrome
from utils.formatting import br_number

# O que a tabela por loja mostra para os produtos marcados.
METRICS = {
    "Estoque": dict(value="quantidade_estoque", kind="stock", emoji="📦",
                    note="Unidades em estoque de cada produto marcado em cada loja."),
    "Vendas": dict(value="quantidade_vendida", kind="units", emoji="🛒",
                   note="Unidades vendidas no período de cada produto marcado em cada loja."),
    "Faturamento": dict(value="valor_vendido", kind="money", emoji="💵",
                        note="Valor vendido no período de cada produto marcado em cada loja."),
}

PICKER_QSS = """
QDialog { background:#F4F7FC; }
QLabel { background:transparent; }
QLabel#pickTitle { color:#12213D; font-size:20px; font-weight:900; }
QLabel#pickHint { color:#7A879D; font-size:11px; }
QLabel#pickCount { color:#2854D9; background:#E8EEFF; border-radius:10px; padding:5px 11px;
    font-size:11px; font-weight:900; }
QListWidget#pickList { background:#FFFFFF; border:1px solid #DCE6F3; border-radius:12px; padding:4px;
    outline:none; }
QListWidget#pickList::item { border:none; border-bottom:1px solid #EEF2F7; border-radius:0; margin:0;
    padding:8px 6px; color:#1B2B47; }
QListWidget#pickList::item:hover { background:#F5F8FF; }
QListWidget#pickList::item:selected { background:#EEF3FF; color:#132E63; border:none; }
"""


class ProductPickerDialog(QDialog):
    """Lista com caixas de marcar; `on_open(códigos, métrica)` abre a tabela dos marcados."""

    def __init__(self, df, on_open, initial_query="", parent=None):
        super().__init__(parent)
        self.df = df
        self.on_open = on_open
        self.options = product_options(df)
        self.checked = set()  # códigos marcados (continuam marcados ao mudar a busca)
        self.setWindowTitle("Selecionar produtos")
        self.resize(760, 640)
        self.setStyleSheet(PICKER_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 14, 14)
        root.setSpacing(10)
        install_mac_window_chrome(self, root)

        head = QHBoxLayout()
        title = QLabel("☑  Selecionar produtos")
        title.setObjectName("pickTitle")
        head.addWidget(title)
        head.addStretch()
        self.count = QLabel()
        self.count.setObjectName("pickCount")
        head.addWidget(self.count)
        root.addLayout(head)
        hint = QLabel("Digite parte do nome ou do código, marque os produtos que quer ver "
                      "(ex.: todos os tamanhos de um conjunto) e clique em Ver selecionados. "
                      "As marcações continuam valendo quando você muda a busca.")
        hint.setObjectName("pickHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.search = QLineEdit(initial_query)
        self.search.setPlaceholderText("🔍  Buscar por nome ou código — ex.: conjunto renda")
        self.search.setClearButtonEnabled(True)
        root.addWidget(self.search)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        mark_all = QPushButton("Marcar todos da busca")
        mark_all.setObjectName("Secondary")
        mark_all.clicked.connect(lambda checked=False: self._set_visible(True))
        tools.addWidget(mark_all)
        unmark = QPushButton("Desmarcar da busca")
        unmark.setObjectName("Ghost")
        unmark.clicked.connect(lambda checked=False: self._set_visible(False))
        tools.addWidget(unmark)
        clear = QPushButton("Limpar seleção")
        clear.setObjectName("Ghost")
        clear.clicked.connect(lambda checked=False: self._clear())
        tools.addWidget(clear)
        self.only_marked = QPushButton("Mostrar só marcados")
        self.only_marked.setObjectName("Ghost")
        self.only_marked.setCheckable(True)
        self.only_marked.toggled.connect(lambda _on: self.refresh())
        tools.addWidget(self.only_marked)
        tools.addStretch()
        root.addLayout(tools)

        self.list = QListWidget()
        self.list.setObjectName("pickList")
        self.list.itemChanged.connect(self._item_changed)
        # Clicar em qualquer ponto da linha marca/desmarca, não só na caixinha.
        self.list.itemClicked.connect(self._toggle_clicked)
        install_copy_shortcut(self.list)  # Ctrl+C copia o código da linha atual
        self.list.setToolTip("Clique para marcar/desmarcar • Ctrl+C copia o código")
        root.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Mostrar:"))
        self.metric = QComboBox()
        self.metric.addItems(list(METRICS))
        bottom.addWidget(self.metric)
        bottom.addStretch()
        cancel = QPushButton("Fechar")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(lambda checked=False: self.reject())
        bottom.addWidget(cancel)
        self.open_button = QPushButton("VER SELECIONADOS")
        self.open_button.clicked.connect(lambda checked=False: self._open())
        bottom.addWidget(self.open_button)
        root.addLayout(bottom)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _text: self._debounce.start())
        self.refresh()
        self.search.setFocus()

    # ---------- lista ----------
    def visible_options(self):
        if self.only_marked.isChecked():
            return [o for o in self.options if o["codigo_barras"] in self.checked]
        return match_options(self.options, self.search.text())

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for option in self.visible_options():
            code = option["codigo_barras"]
            item = QListWidgetItem(f"{option['descricao']}   •   {code}   •   {option['subclasse']}")
            item.setData(Qt.ItemDataRole.UserRole, code)
            # Sem ItemIsUserCheckable: quem alterna é o clique na linha (evita alternar duas vezes).
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked if code in self.checked else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._update_count()

    def _item_changed(self, item):
        code = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.checked.add(code)
        else:
            self.checked.discard(code)
        self._update_count()

    def _toggle_clicked(self, item):
        # A caixinha é desenhada pelo estado do item; o clique em qualquer ponto da linha alterna.
        item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                           else Qt.CheckState.Checked)

    def _set_visible(self, checked):
        for option in self.visible_options():
            (self.checked.add if checked else self.checked.discard)(option["codigo_barras"])
        self.refresh()

    def _clear(self):
        self.checked.clear()
        self.only_marked.setChecked(False)
        self.refresh()

    def _update_count(self):
        n = len(self.checked)
        self.count.setText(f"{br_number(n, 0)} marcado{'s' if n != 1 else ''}")
        self.open_button.setEnabled(bool(n))

    def _open(self):
        if self.checked:
            self.on_open(sorted(self.checked), self.metric.currentText(), self)

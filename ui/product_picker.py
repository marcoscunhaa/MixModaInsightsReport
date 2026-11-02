"""Seleção de produtos para a análise.

Pedido da loja: na busca por nome, marcar os produtos que interessam (como
grifar no Excel), por exemplo todos os tamanhos de um conjunto, e ver o
dashboard só com eles. A tela tem dois lados: à esquerda a busca com os
resultados (menor código primeiro, então a grade fica P → GG); à direita o que
já foi marcado, que continua marcado ao mudar a busca. "Aplicar à análise"
devolve os códigos e o dashboard inteiro passa a considerar só esses produtos.
"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from core.analyzer import match_options, product_options
from ui.copyable import install_copy_shortcut
from ui.window_chrome import install_mac_window_chrome
from utils.formatting import br_number

SHOW_LIMIT = 300  # linhas desenhadas por vez; a busca refina o resto

PICKER_QSS = """
QDialog { background:#F4F7FC; }
QLabel { background:transparent; }
QFrame#pickHero { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1E3A8A,stop:0.6 #2F5BEA,stop:1 #6D5BF0);
    border-radius:20px; }
QLabel#heroEyebrow { color:#C9D6FF; font-size:10px; font-weight:900; letter-spacing:1.5px; }
QLabel#heroTitle { color:#FFFFFF; font-size:22px; font-weight:900; }
QLabel#heroText { color:#E3E9FF; font-size:12px; }
QLabel#heroBadge { background:rgba(255,255,255,0.16); color:#FFFFFF; border-radius:14px;
    padding:8px 16px; font-size:13px; font-weight:900; }

QFrame#pickPanel { background:#FFFFFF; border:1px solid #DFE7F3; border-radius:18px; }
QLabel#panelTitle { color:#142B52; font-size:13px; font-weight:900; }
QLabel#panelMeta { color:#7A879D; font-size:11px; font-weight:700; }

QLineEdit#pickSearch { background:#F6F8FC; border:1px solid #DCE4F0; border-radius:14px;
    padding:12px 14px; font-size:13px; color:#16233F; }
QLineEdit#pickSearch:focus { background:#FFFFFF; border:1px solid #6E8DFF; }

QListWidget#pickList, QListWidget#chosenList { background:transparent; border:none; outline:none; }
QListWidget#pickList::item, QListWidget#chosenList::item { border:none; margin:0; padding:0;
    background:transparent; }
QListWidget#pickList::item:selected, QListWidget#chosenList::item:selected { background:transparent; border:none; }

QFrame#row { background:#FFFFFF; border:1px solid #EDF1F7; border-radius:12px; }
QFrame#row:hover { background:#F7F9FF; border:1px solid #C9D6FF; }
QFrame#row[checked="true"] { background:#EEF3FF; border:1px solid #9DB3FF; }
QLabel#check { border:2px solid #C3CEDF; border-radius:11px; background:#FFFFFF; color:transparent;
    font-size:12px; font-weight:900; }
QFrame#row[checked="true"] QLabel#check { background:#2F5BEA; border:2px solid #2F5BEA; color:#FFFFFF; }
QLabel#rowName { color:#16233F; font-size:12px; font-weight:800; }
QLabel#rowCode { color:#7A879D; font-size:11px; font-weight:600; }
QLabel#rowPill { color:#4C5BD4; background:#EEF0FF; border-radius:9px; padding:3px 9px;
    font-size:10px; font-weight:800; }

QFrame#chosen { background:#F7F9FD; border:1px solid #E6ECF5; border-radius:11px; }
QLabel#chosenName { color:#16233F; font-size:11px; font-weight:800; }
QLabel#chosenCode { color:#8794A9; font-size:10px; }
QPushButton#remove { background:transparent; color:#9AA6BA; border:none; border-radius:10px;
    padding:2px 7px; font-size:14px; font-weight:900; }
QPushButton#remove:hover { background:#FFE8EC; color:#D9284B; }

QPushButton#link { background:transparent; color:#2F5BEA; border:none; padding:4px 6px;
    font-size:11px; font-weight:900; }
QPushButton#link:hover { color:#1B3EAF; text-decoration:underline; }
QPushButton#link:disabled { color:#B4BECD; }
QPushButton#apply { background:#2F5BEA; color:#FFFFFF; border:none; border-radius:12px;
    padding:12px 22px; font-weight:900; }
QPushButton#apply:hover { background:#244DD0; }
QPushButton#cancel { background:#FFFFFF; color:#40516E; border:1px solid #D8E2F0; border-radius:12px;
    padding:12px 18px; font-weight:800; }
QPushButton#cancel:hover { background:#EEF4FF; color:#2854D9; border-color:#AFC2FF; }
QLabel#empty { color:#8A96AA; font-size:12px; padding:30px 10px; }
"""


def _restyle(widget):
    """Reaplica o QSS depois de mudar a propriedade `checked` (o Qt não refaz sozinho)."""
    for w in (widget, *widget.findChildren(QLabel)):
        w.style().unpolish(w)
        w.style().polish(w)


class _ResultRow(QFrame):
    """Linha de resultado: círculo de marcação, nome, código e subclasse."""

    def __init__(self, option, checked):
        super().__init__()
        self.setObjectName("row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(12)
        self.check = QLabel("✓")
        self.check.setObjectName("check")
        self.check.setFixedSize(22, 22)
        self.check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.check)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        name = QLabel(option["descricao"])
        name.setObjectName("rowName")
        texts.addWidget(name)
        code = QLabel(option["codigo_barras"])
        code.setObjectName("rowCode")
        texts.addWidget(code)
        layout.addLayout(texts, 1)
        if option.get("subclasse") and option["subclasse"] != "nan":
            pill = QLabel(option["subclasse"])
            pill.setObjectName("rowPill")
            layout.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        # O clique atravessa os textos e a linha (QFrame não o consome) e chega na
        # lista, que marca/desmarca; a linha continua recebendo o hover.
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.set_checked(checked)

    def set_checked(self, checked):
        self.setProperty("checked", "true" if checked else "false")
        _restyle(self)


class _ChosenRow(QFrame):
    """Item na coluna "Selecionados", com ✕ para tirar."""

    def __init__(self, option, on_remove):
        super().__init__()
        self.setObjectName("chosen")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(6)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(option["descricao"])
        name.setObjectName("chosenName")
        texts.addWidget(name)
        code = QLabel(option["codigo_barras"])
        code.setObjectName("chosenCode")
        texts.addWidget(code)
        layout.addLayout(texts, 1)
        remove = QPushButton("✕")
        remove.setObjectName("remove")
        remove.setToolTip("Tirar da seleção")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.clicked.connect(lambda checked=False: on_remove(option["codigo_barras"]))
        layout.addWidget(remove, 0, Qt.AlignmentFlag.AlignVCenter)


class ProductPickerDialog(QDialog):
    """Escolhe os produtos da análise. Depois do `exec()`, `selected` tem os códigos (vazio = todos)."""

    def __init__(self, df, selected=(), initial_query="", parent=None):
        super().__init__(parent)
        self.options = product_options(df)
        self.by_code = {o["codigo_barras"]: o for o in self.options}
        self.checked = {code for code in selected if code in self.by_code}
        self.selected = set(self.checked)
        self._rows = {}
        self.setWindowTitle("Selecionar produtos")
        self.resize(1040, 720)
        self.setMinimumSize(760, 520)
        self.setStyleSheet(PICKER_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 14, 14)
        root.setSpacing(14)
        install_mac_window_chrome(self, root)
        root.addWidget(self._hero())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._results_panel(initial_query), 3)
        body.addWidget(self._chosen_panel(), 2)
        root.addLayout(body, 1)
        root.addLayout(self._footer())

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(140)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _text: self._debounce.start())
        self.refresh()
        self.refresh_chosen()
        self.search.setFocus()
        self.search.selectAll()

    # ---------- montagem ----------
    def _hero(self):
        hero = QFrame()
        hero.setObjectName("pickHero")
        row = QHBoxLayout(hero)
        row.setContentsMargins(24, 18, 24, 18)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        eyebrow = QLabel("FOCO DA ANÁLISE")
        eyebrow.setObjectName("heroEyebrow")
        texts.addWidget(eyebrow)
        title = QLabel("Selecionar produtos")
        title.setObjectName("heroTitle")
        texts.addWidget(title)
        text = QLabel("Busque e marque os produtos que quer acompanhar — por exemplo, todos os "
                      "tamanhos de um conjunto. O dashboard inteiro passa a mostrar só eles.")
        text.setObjectName("heroText")
        text.setWordWrap(True)
        texts.addWidget(text)
        row.addLayout(texts, 1)
        self.hero_badge = QLabel()
        self.hero_badge.setObjectName("heroBadge")
        row.addWidget(self.hero_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        return hero

    def _results_panel(self, initial_query):
        panel = QFrame()
        panel.setObjectName("pickPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        self.search = QLineEdit(initial_query)
        self.search.setObjectName("pickSearch")
        self.search.setPlaceholderText("🔍   Buscar por nome ou código  —  ex.: conjunto renda")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        meta = QHBoxLayout()
        self.results_meta = QLabel()
        self.results_meta.setObjectName("panelMeta")
        meta.addWidget(self.results_meta, 1)
        self.mark_all = QPushButton()
        self.mark_all.setObjectName("link")
        self.mark_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_all.clicked.connect(lambda checked=False: self._mark_visible())
        meta.addWidget(self.mark_all)
        layout.addLayout(meta)

        self.list = QListWidget()
        self.list.setObjectName("pickList")
        self.list.setSpacing(3)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.itemClicked.connect(self._toggle_item)
        install_copy_shortcut(self.list)
        self.list.setToolTip("Clique para marcar ou desmarcar • Ctrl+C copia o código")
        layout.addWidget(self.list, 1)
        self.empty = QLabel("Nenhum produto encontrado.\nTente outra palavra ou parte do código.")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        layout.addWidget(self.empty, 1)
        return panel

    def _chosen_panel(self):
        panel = QFrame()
        panel.setObjectName("pickPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("✓  Selecionados")
        title.setObjectName("panelTitle")
        head.addWidget(title, 1)
        self.clear_button = QPushButton("Limpar tudo")
        self.clear_button.setObjectName("link")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(lambda checked=False: self._clear())
        head.addWidget(self.clear_button)
        layout.addLayout(head)
        self.chosen_meta = QLabel()
        self.chosen_meta.setObjectName("panelMeta")
        self.chosen_meta.setWordWrap(True)
        layout.addWidget(self.chosen_meta)
        self.chosen = QListWidget()
        self.chosen.setObjectName("chosenList")
        self.chosen.setSpacing(3)
        self.chosen.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        install_copy_shortcut(self.chosen)
        layout.addWidget(self.chosen, 1)
        self.chosen_empty = QLabel("Nada marcado ainda.\n\nSem seleção, a análise\nconsidera todos os produtos.")
        self.chosen_empty.setObjectName("empty")
        self.chosen_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.chosen_empty, 1)
        return panel

    def _footer(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        tip = QLabel("Dica: as marcações continuam valendo quando você muda a busca.")
        tip.setObjectName("panelMeta")
        row.addWidget(tip, 1)
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(lambda checked=False: self.reject())
        row.addWidget(cancel)
        self.apply_button = QPushButton()
        self.apply_button.setObjectName("apply")
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(lambda checked=False: self._apply())
        row.addWidget(self.apply_button)
        return row

    # ---------- resultados ----------
    def visible_options(self):
        return match_options(self.options, self.search.text())

    def refresh(self):
        found = self.visible_options()
        shown = found[:SHOW_LIMIT]
        self.list.setUpdatesEnabled(False)
        self.list.clear()
        self._rows = {}
        for option in shown:
            code = option["codigo_barras"]
            item = QListWidgetItem(f"{option['descricao']}  •  {code}")
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setSizeHint(QSize(0, 58))
            self.list.addItem(item)
            row = _ResultRow(option, code in self.checked)
            self.list.setItemWidget(item, row)
            self._rows[code] = row
        self.list.setUpdatesEnabled(True)
        self.list.setVisible(bool(shown))
        self.empty.setVisible(not shown)
        extra = f" — mostrando os primeiros {SHOW_LIMIT}, refine a busca" if len(found) > SHOW_LIMIT else ""
        self.results_meta.setText(f"{br_number(len(found), 0)} produto{'s' if len(found) != 1 else ''}{extra}")
        self._update_actions()

    def _toggle_item(self, item):
        self.toggle(item.data(Qt.ItemDataRole.UserRole))

    def toggle(self, code):
        if code in self.checked:
            self.checked.discard(code)
        else:
            self.checked.add(code)
        if code in self._rows:
            self._rows[code].set_checked(code in self.checked)
        self.refresh_chosen()

    def _mark_visible(self):
        visible = [o["codigo_barras"] for o in self.visible_options()]
        if visible and all(code in self.checked for code in visible):
            self.checked.difference_update(visible)
        else:
            self.checked.update(visible)
        for code, row in self._rows.items():
            row.set_checked(code in self.checked)
        self.refresh_chosen()

    def _clear(self):
        self.checked.clear()
        for row in self._rows.values():
            row.set_checked(False)
        self.refresh_chosen()

    # ---------- selecionados ----------
    def refresh_chosen(self):
        chosen = [o for o in self.options if o["codigo_barras"] in self.checked]  # já em ordem de código
        self.chosen.clear()
        for option in chosen:
            item = QListWidgetItem(f"{option['descricao']}  •  {option['codigo_barras']}")
            item.setSizeHint(QSize(0, 46))
            self.chosen.addItem(item)
            self.chosen.setItemWidget(item, _ChosenRow(option, self.toggle))
        n = len(chosen)
        self.chosen.setVisible(bool(n))
        self.chosen_empty.setVisible(not n)
        self.chosen_meta.setText(
            f"{br_number(n, 0)} produto{'s' if n != 1 else ''} na análise, em ordem de código (P → GG)."
            if n else "Marque produtos à esquerda.")
        self.clear_button.setEnabled(bool(n))
        self.hero_badge.setText(f"{br_number(n, 0)} selecionado{'s' if n != 1 else ''}" if n else "Todos os produtos")
        self._update_actions()

    def _update_actions(self):
        visible = [o["codigo_barras"] for o in self.visible_options()]
        all_marked = bool(visible) and all(code in self.checked for code in visible)
        self.mark_all.setEnabled(bool(visible))
        self.mark_all.setText(f"Desmarcar os {br_number(len(visible), 0)}" if all_marked
                              else f"Marcar todos ({br_number(len(visible), 0)})")
        n = len(self.checked)
        self.apply_button.setText(f"APLICAR À ANÁLISE  ·  {br_number(n, 0)}" if n else "VER TODOS OS PRODUTOS")

    def _apply(self):
        self.selected = set(self.checked)
        self.accept()

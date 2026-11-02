"""Código de barras copiável em qualquer lista do app.

- Tabelas e listas: dois cliques no código abrem um campo só de leitura com o
  código já selecionado; Ctrl+C copia. Com a célula apenas selecionada (um
  clique), Ctrl+C também copia o texto dela.
- Textos (QLabel) de cards: dois cliques selecionam o código; Ctrl+C copia.

Nada aqui altera dados: o campo é só de leitura e nunca grava no modelo.
"""
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QStyledItemDelegate

COPY_TIP = "Dois cliques para selecionar o código • Ctrl+C para copiar"

_DIGITS = re.compile(r"\d{4,}")

_EDITOR_QSS = (
    "QLineEdit{background:#FFFFFF;color:#12213D;border:2px solid #315BEA;border-radius:4px;"
    "padding:0 6px;selection-background-color:#315BEA;selection-color:#FFFFFF;}"
)


def barcode_span(text):
    """(início, tamanho) do código dentro do texto: a maior sequência de dígitos.

    Em "SUTIA PROMO  •  7896722660034" seleciona só o código; sem dígitos, tudo.
    """
    text = str(text or "")
    best = max(_DIGITS.finditer(text), key=lambda m: len(m.group()), default=None)
    if best is None:
        return 0, len(text)
    return best.start(), best.end() - best.start()


class _NoEditorDelegate(QStyledItemDelegate):
    """Demais colunas: dois cliques não abrem editor (a tabela continua só leitura)."""

    def createEditor(self, parent, option, index):
        return None


class _CopyEditorDelegate(QStyledItemDelegate):
    """Abre um QLineEdit só de leitura com o código selecionado."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        editor.setFrame(False)
        editor.setStyleSheet(_EDITOR_QSS)
        editor.setToolTip("Ctrl+C para copiar • Esc para fechar")
        return editor

    def setEditorData(self, editor, index):
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        editor.setText(text)
        start, length = barcode_span(text)

        def select(e=editor):
            try:
                e.setSelection(start, length)
            except RuntimeError:  # editor já fechado
                pass

        select()
        QTimer.singleShot(0, select)  # o foco ao abrir pode desfazer a seleção

    def setModelData(self, editor, model, index):
        pass  # nunca altera o dado


def _copy_current(view):
    index = view.currentIndex()
    if not index.isValid():
        return
    text = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
    if text:
        start, length = barcode_span(text)
        has_code = length and length < len(text) and _DIGITS.fullmatch(text[start:start + length])
        QGuiApplication.clipboard().setText(text[start:start + length] if has_code else text)


def install_copy_shortcut(view):
    """Ctrl+C na lista/tabela copia o código (ou o texto) do item atual."""
    if getattr(view, "_copy_shortcut", None) is not None:
        return
    shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), view)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    shortcut.activated.connect(lambda v=view: _copy_current(v))
    view._copy_shortcut = shortcut


def make_barcode_copyable(view, column):
    """Tabela só leitura onde a coluna `column` (código de barras) pode ser selecionada e copiada."""
    view._no_editor_delegate = _NoEditorDelegate(view)
    view._copy_delegate = _CopyEditorDelegate(view)
    view.setItemDelegate(view._no_editor_delegate)
    view.setItemDelegateForColumn(column, view._copy_delegate)
    view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
    view._barcode_column = column
    install_copy_shortcut(view)
    tip_item = view.horizontalHeaderItem(column) if hasattr(view, "horizontalHeaderItem") else None
    if tip_item is not None:
        tip_item.setToolTip(COPY_TIP)


def make_list_copyable(list_widget):
    """QListWidget cujo texto dos itens traz o código: dois cliques selecionam o código.

    Os itens precisam da flag ItemIsEditable (use `copyable_flags`).
    """
    list_widget._copy_delegate = _CopyEditorDelegate(list_widget)
    list_widget.setItemDelegate(list_widget._copy_delegate)
    list_widget.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
    install_copy_shortcut(list_widget)
    list_widget.setToolTip(COPY_TIP)


def copyable_flags(item):
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
    return item


def is_barcode_column(view, column):
    return getattr(view, "_barcode_column", None) == column


def make_label_copyable(label):
    """Texto de card com o código: dois cliques selecionam a palavra (o código), Ctrl+C copia."""
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setToolTip(COPY_TIP)
    return label

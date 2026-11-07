"""Lista de produtos sem classificação (mesmo formato dos alertas) e Excel para cadastro.

Um produto por código de barras, com as lojas em que aparece, totais somados e a
sugestão de grupo/subclasse. Clicar abre o card do produto; o botão gera o Excel
(uma aba por loja) e abre o arquivo.
"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.unclassified import ClassificationSuggester, merge_by_barcode, unclassified_rows
from ui.copyable import is_barcode_column, make_barcode_copyable
from ui.window_chrome import get_save_file, install_mac_window_chrome, show_message
from utils.formatting import br_number, brl
from utils.normalization import normalize_barcode, normalize_text

PALETTE = """
QDialog { background:#F3F6FB; }
QLabel#eyebrow { color:#C46A10; font-size:10px; font-weight:900; letter-spacing:1px; }
QLabel#title { color:#14284B; font-size:24px; font-weight:900; }
QLabel#muted { color:#74829A; font-size:11px; }
QFrame#panel { background:#FFFFFF; border:1px solid #E0E7F1; border-radius:16px; }
QLineEdit, QComboBox { background:#F8FAFD; border:1px solid #DCE4F0; border-radius:9px; padding:9px 10px; color:#233451; }
QLineEdit:focus, QComboBox:focus { border:1px solid #5675E8; background:#FFFFFF; }
QTableWidget { background:#FFFFFF; border:1px solid #E2E8F1; border-radius:10px; }
QLabel#chip { background:#FFF7E0; border:1px solid #F3D28B; border-radius:12px; padding:6px 12px;
    color:#A35A00; font-size:11px; font-weight:900; }
"""

HEADERS = ["Produto", "Código", "Lojas", "Estoque", "Vendas", "Preço de venda", "Sugestão de classificação"]


def export_unclassified_excel(parent, df, catalog, open_after=True):
    """Salva o Excel de produtos sem classificação (uma aba por loja) e o abre."""
    from exports.unclassified_export import export_unclassified_xlsx
    if unclassified_rows(df).empty:
        show_message(parent, "information", "Sem pendências", "Nenhum produto sem classificação nesta análise.")
        return ""
    path = get_save_file(parent, "Salvar Excel para cadastro", "Produtos_sem_classificacao.xlsx", "Excel (*.xlsx)", "xlsx")
    if not path:
        return ""
    try:
        export_unclassified_xlsx(path, df, catalog)
    except PermissionError:
        show_message(parent, "critical", "Não foi possível salvar o Excel",
                     "O arquivo está aberto em outro programa. Feche-o ou escolha outro nome e tente de novo.")
        return ""
    except Exception as error:
        show_message(parent, "critical", "Não foi possível gerar o Excel", f"{type(error).__name__}: {error}")
        return ""
    if not (open_after and QDesktopServices.openUrl(QUrl.fromLocalFile(path))):
        show_message(parent, "information", "Excel gerado",
                     f"Arquivo salvo em:\n{path}\n\nPreencha GRUPO e SUBCLASSE e importe em "
                     "Explorar estoque › IMPORTAR CLASSIFICAÇÕES.")
    return path


class UnclassifiedDialog(QDialog):
    def __init__(self, df, catalog=None, parent=None):
        super().__init__(parent)
        self.df = df
        self.catalog = catalog
        self.products = merge_by_barcode(unclassified_rows(df))
        suggester = ClassificationSuggester(catalog)
        for product in self.products:
            hint = suggester.suggest(product["descricao"])
            product["_sugestao"] = f"{hint[0]} › {hint[1]}" if hint else "—"
        self.setWindowTitle("Produtos sem classificação • Mix Moda")
        self.resize(1080, 640)
        self.setMinimumSize(760, 460)
        self.setStyleSheet(PALETTE)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(12)
        install_mac_window_chrome(self, root)

        eyebrow = QLabel("CADASTRO DE PRODUTOS")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)
        title = QLabel("Produtos sem classificação")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel(
            "Produtos da análise sem grupo ou subclasse no catálogo. Cada código aparece uma vez, "
            "com as lojas em que está e os totais somados. Clique num produto para ver os detalhes por loja."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        stores = []
        for product in self.products:
            for store in product["lojas"]:
                if store not in stores:
                    stores.append(store)
        from core.stores import order_stores
        stores = order_stores(stores)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for store in stores:
            n = sum(store in p["lojas"] for p in self.products)
            chip = QLabel(f"🏬  {store}  ·  {br_number(n, 0)}")
            chip.setObjectName("chip")
            chips.addWidget(chip)
        chips.addStretch()
        root.addLayout(chips)

        filters = QHBoxLayout()
        self.store = QComboBox()
        self.store.addItem("Todas as lojas")
        self.store.addItems(stores)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar produto ou código...")
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.store)
        filters.addWidget(self.search, 1)
        root.addLayout(filters)

        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        header = self.table.horizontalHeader()
        for col in range(len(HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        make_barcode_copyable(self.table, 1)
        self.table.cellClicked.connect(self.open_product)
        layout.addWidget(self.table, 1)
        self.empty = QLabel("Tudo classificado")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("color:#16836D;font-size:18px;font-weight:900;padding:28px;")
        layout.addWidget(self.empty)
        root.addWidget(panel, 1)

        footer = QHBoxLayout()
        self.count = QLabel()
        self.count.setObjectName("muted")
        footer.addWidget(self.count, 1)
        excel = QPushButton("📊  ABRIR EXCEL PARA CADASTRO")
        excel.setEnabled(bool(self.products))
        excel.setCursor(Qt.CursorShape.PointingHandCursor)
        excel.setToolTip("Gera um Excel com uma aba por loja, sugestão de grupo/subclasse e colunas para preencher, e abre o arquivo.")
        excel.setStyleSheet(
            "QPushButton{background:#16836D;color:white;border:0;border-radius:10px;padding:9px 15px;font-weight:900;}"
            "QPushButton:hover{background:#106B59;}"
            "QPushButton:disabled{background:#D8E0E9;color:#8793A5;}"
        )
        excel.clicked.connect(lambda: export_unclassified_excel(self, self.df, self.catalog))
        footer.addWidget(excel)
        close = QPushButton("FECHAR")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        self.store.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def visible_products(self):
        store = self.store.currentText()
        words = normalize_text(self.search.text()).split()
        digits = normalize_barcode(self.search.text()) if any(ch.isdigit() for ch in self.search.text()) else ""
        shown = []
        for product in self.products:
            if store != "Todas as lojas" and store not in product["lojas"]:
                continue
            text = normalize_text(f"{product['descricao']} {product['codigo_barras']}")
            if words and not (all(w in text for w in words) or (digits not in ("", "0") and digits in normalize_barcode(product["codigo_barras"]))):
                continue
            shown.append(product)
        return shown

    def refresh(self):
        self.shown = self.visible_products()
        self.table.setRowCount(len(self.shown))
        bold = QFont("Segoe UI", 9, QFont.Weight.Bold)
        for row, p in enumerate(self.shown):
            values = [
                p["descricao"], p["codigo_barras"], p["loja"],
                br_number(p["quantidade_estoque"], 0), br_number(p["quantidade_vendida"], 0),
                brl(p["preco_venda"]), p["_sugestao"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3 and p["quantidade_estoque"] < 0:
                    item.setForeground(QColor("#B91C3A")); item.setFont(bold)
                if col == 6:
                    item.setForeground(QColor("#8A94A8" if value == "—" else "#2854D9"))
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 40)
        self.table.setVisible(bool(self.products))
        self.empty.setVisible(not self.products)
        total = len(self.products)
        self.count.setText(
            f"{br_number(len(self.shown), 0)} de {br_number(total, 0)} produto(s) sem classificação"
            if len(self.shown) != total else f"{br_number(total, 0)} produto(s) sem classificação"
        )

    def open_product(self, row, col):
        if is_barcode_column(self.table, col) or not (0 <= row < len(self.shown)):
            return
        from ui.product_modal import ProductModal
        ProductModal(self.shown[row], self).exec()

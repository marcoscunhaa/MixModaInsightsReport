"""Nova análise em três passos: período → lojas e planilhas → gerar o dashboard.

A tela guia quem não é da área: cada passo tem número e uma frase do que fazer,
cada planilha mostra se já foi escolhida (✓ verde) e o botão de gerar diz o que
ainda falta. O comportamento é o mesmo de antes: até uma linha por loja, cada
loja uma vez, e o sinal `generate` leva lojas, planilhas e datas.
"""
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.stores import STORES
from ui.ui_kit import PageHeader, button, step_header
from ui.window_chrome import get_open_file, show_message

FILE_STYLE = {
    False: "background:#F4F7FC;border:1px dashed #C9D5EA;border-radius:10px;padding:8px 12px;"
           "color:#7A879D;font-size:12px;font-weight:700;",
    True: "background:#E8FAF5;border:1px solid #9FE3D2;border-radius:10px;padding:8px 12px;"
          "color:#087F6A;font-size:12px;font-weight:800;",
}


class StoreRow(QFrame):
    remove = Signal(object)
    changed = Signal()

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.index = index
        self.stock_path = None
        self.sales_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)

        head = QHBoxLayout()
        self.title = QLabel(f"🏬  LOJA {index}")
        self.title.setStyleSheet("font-size:14px;font-weight:900;color:#17326F;")
        head.addWidget(self.title)
        head.addStretch()
        self.remove_button = button("✕  Remover esta loja", "Link", "Tirar esta loja da análise",
                                    lambda: self.remove.emit(self))
        self.remove_button.setStyleSheet("QPushButton{color:#D9284B;} QPushButton:hover{color:#A8183A;}")
        head.addWidget(self.remove_button)
        layout.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        store_label = QLabel("Qual loja?")
        store_label.setObjectName("FieldLabel")
        self.loja = QComboBox()
        self.loja.addItem("Selecione uma loja", "")
        for store in STORES:
            self.loja.addItem(store, store)
        self.loja.setToolTip("Escolha a loja destas planilhas")
        self.loja.currentIndexChanged.connect(lambda _i: self.changed.emit())
        grid.addWidget(store_label, 0, 0)
        grid.addWidget(self.loja, 0, 1, 1, 2)

        stock_label = QLabel("Planilha de estoque")
        stock_label.setObjectName("FieldLabel")
        self.stock = QLabel("Nenhum arquivo escolhido")
        self.stock.setStyleSheet(FILE_STYLE[False])
        bs = button("📦  Escolher arquivo", "Secondary", "Planilha de estoque da loja (XLS ou XLSX)", self.pick_stock)
        grid.addWidget(stock_label, 1, 0)
        grid.addWidget(self.stock, 1, 1)
        grid.addWidget(bs, 1, 2)

        sales_label = QLabel("Planilha de vendas")
        sales_label.setObjectName("FieldLabel")
        self.sales = QLabel("Nenhum arquivo escolhido")
        self.sales.setStyleSheet(FILE_STYLE[False])
        bv = button("🛒  Escolher arquivo", "Secondary", "Planilha de vendas da loja no período (XLS ou XLSX)",
                    self.pick_sales)
        grid.addWidget(sales_label, 2, 0)
        grid.addWidget(self.sales, 2, 1)
        grid.addWidget(bv, 2, 2)
        layout.addLayout(grid)

    def set_index(self, index):
        self.index = index
        self.title.setText(f"🏬  LOJA {index}")

    def is_complete(self):
        return bool(self.loja.currentData() and self.stock_path and self.sales_path)

    def _pick(self, title):
        try:
            return get_open_file(self, title, "Planilhas (*.xlsx *.xls)")
        except Exception as error:
            show_message(self, "critical", "Não foi possível abrir os arquivos", str(error))
            return ""

    def pick_stock(self):
        path = self._pick("Selecionar estoque")
        if path:
            self.stock_path = path
            self.stock.setText("✓  " + Path(path).name)
            self.stock.setStyleSheet(FILE_STYLE[True])
            self.stock.setToolTip(path)
            self.changed.emit()

    def pick_sales(self):
        path = self._pick("Selecionar vendas")
        if path:
            self.sales_path = path
            self.sales.setText("✓  " + Path(path).name)
            self.sales.setStyleSheet(FILE_STYLE[True])
            self.sales.setToolTip(path)
            self.changed.emit()


class AnalysisPage(QWidget):
    generate = Signal(dict)

    def __init__(self, parent=None, on_home=None):
        super().__init__(parent)
        self.rows = []
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 22)
        root.setSpacing(14)

        header = PageHeader("Nova análise", "Cruze estoque e vendas e gere o dashboard em 3 passos.",
                            "← Início", on_home or (lambda: None))
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("Transparent")
        body = QVBoxLayout(inner)
        body.setContentsMargins(2, 2, 10, 2)
        body.setSpacing(14)

        # Passo 1 — período
        period = QFrame()
        period.setObjectName("Panel")
        pbox = QVBoxLayout(period)
        pbox.setContentsMargins(20, 16, 20, 18)
        pbox.setSpacing(12)
        pbox.addLayout(step_header(1, "Escolha o período", "As datas das vendas que você exportou do sistema."))
        dates = QHBoxLayout()
        dates.setSpacing(12)
        self.ini = QDateEdit(QDate.currentDate().addMonths(-1))
        self.ini.setCalendarPopup(True)
        self.ini.setDisplayFormat("dd/MM/yyyy")
        self.fim = QDateEdit(QDate.currentDate())
        self.fim.setCalendarPopup(True)
        self.fim.setDisplayFormat("dd/MM/yyyy")
        for caption, field in (("De", self.ini), ("Até", self.fim)):
            label = QLabel(caption)
            label.setObjectName("FieldLabel")
            dates.addWidget(label)
            field.setMinimumWidth(160)
            dates.addWidget(field)
            dates.addSpacing(8)
        dates.addStretch()
        pbox.addLayout(dates)
        body.addWidget(period)

        # Passo 2 — lojas
        stores_box = QVBoxLayout()
        stores_box.setSpacing(4)
        stores_box.addLayout(step_header(
            2, "Adicione as lojas e as planilhas",
            f"Para cada loja, escolha a planilha de estoque e a de vendas. Dá para analisar até {len(STORES)} "
            "lojas juntas, cada uma uma vez.",
        ))
        body.addLayout(stores_box)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(12)
        body.addLayout(self.rows_layout)
        add_row = QHBoxLayout()
        self.add_button = button("＋  Adicionar outra loja", "Success", "Incluir mais uma loja nesta análise",
                                 self.add_store)
        add_row.addWidget(self.add_button)
        add_row.addStretch()
        body.addLayout(add_row)
        body.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Passo 3 — gerar (sempre visível no rodapé)
        footer = QFrame()
        footer.setObjectName("Panel")
        fbox = QHBoxLayout(footer)
        fbox.setContentsMargins(20, 14, 16, 14)
        fbox.setSpacing(12)
        badge = QLabel("3")
        badge.setObjectName("StepBadge")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fbox.addWidget(badge)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        step = QLabel("Gere o dashboard")
        step.setObjectName("StepTitle")
        texts.addWidget(step)
        self.ready_hint = QLabel()
        self.ready_hint.setObjectName("SectionHint")
        texts.addWidget(self.ready_hint)
        fbox.addLayout(texts, 1)
        self.generate_button = button("📊  Gerar dashboard  →", "Primary",
                                      "Lê as planilhas, cruza estoque e vendas e abre o dashboard", self.submit)
        self.generate_button.setMinimumHeight(44)
        fbox.addWidget(self.generate_button)
        root.addWidget(footer)

        self.add_store()

    def add_store(self):
        if len(self.rows) >= len(STORES):
            return
        row = StoreRow(len(self.rows) + 1)
        row.remove.connect(self.remove_store)
        row.changed.connect(self._update_state)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self._update_state()

    def remove_store(self, row):
        if len(self.rows) <= 1:
            return
        self.rows.remove(row)
        row.deleteLater()
        for i, r in enumerate(self.rows, 1):
            r.set_index(i)
        self._update_state()

    def _update_state(self):
        """Mostra o que falta e esconde ações que não fazem sentido agora."""
        self.add_button.setEnabled(len(self.rows) < len(STORES))
        self.add_button.setText("＋  Adicionar outra loja" if len(self.rows) < len(STORES)
                                else f"Limite de {len(STORES)} lojas atingido")
        for row in self.rows:
            row.remove_button.setVisible(len(self.rows) > 1)
        missing = sum(not r.is_complete() for r in self.rows)
        n = len(self.rows)
        self.ready_hint.setText(
            f"Tudo pronto: {n} loja{'s' if n != 1 else ''} com estoque e vendas." if not missing else
            f"Falta completar {missing} loja{'s' if missing != 1 else ''}: escolha a loja e as duas planilhas."
        )
        self.ready_hint.setStyleSheet("color:#087F6A;font-weight:800;" if not missing else "")

    def submit(self):
        if self.ini.date() > self.fim.date():
            show_message(self, "warning", "Período inválido", "A data inicial não pode ser posterior à final.")
            return
        stores = []
        for r in self.rows:
            loja = r.loja.currentData()
            if not loja or not r.stock_path or not r.sales_path:
                show_message(self, "warning", "Dados incompletos", "Preencha loja, estoque e vendas de todas as lojas.")
                return
            stores.append({"loja": loja, "estoque_path": r.stock_path, "vendas_path": r.sales_path})
        selected = [s["loja"] for s in stores]
        if len(selected) != len(set(selected)):
            show_message(self, "warning", "Loja repetida", "Selecione cada loja no máximo uma vez.")
            return
        # A análise roda em segundo plano; a janela principal chama set_busy/set_progress.
        self.generate.emit({"lojas": stores, "data_inicio": self.ini.date().toPython(),
                            "data_fim": self.fim.date().toPython()})

    def set_busy(self, busy):
        """Botão travado e com progresso enquanto a análise roda em segundo plano."""
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText("⏳  Preparando…" if busy else "📊  Gerar dashboard  →")

    def set_progress(self, text, done, total):
        percent = int(done * 100 / total) if total else 0
        self.generate_button.setText(f"⏳  {text}…  {percent}%")

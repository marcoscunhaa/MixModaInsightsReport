"""Roda a análise numa QThread para a janela continuar respondendo.

Sinais (entregues na thread da tela):
- `progress(texto, feito, total)` a cada etapa;
- `succeeded(frame, audit)` no fim;
- `failed(mensagem, detalhes)` se algo der errado.
"""
import traceback

from PySide6.QtCore import QThread, Signal

from core.analysis_job import run_analysis


class AnalysisWorker(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal(object, object)
    failed = Signal(str, str)

    def __init__(self, info, catalog, classification, parent=None):
        super().__init__(parent)
        self.info, self.catalog, self.classification = info, catalog, classification

    def run(self):
        try:
            frame, audit = run_analysis(self.info, self.catalog, self.classification,
                                        lambda text, done, total: self.progress.emit(text, done, total))
        except Exception as error:  # qualquer erro vira mensagem na tela, nunca derruba o app
            self.failed.emit(f"{type(error).__name__}: {error}", traceback.format_exc())
            return
        self.succeeded.emit(frame, audit)

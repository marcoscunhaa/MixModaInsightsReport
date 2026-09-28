import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def resource_path(relative):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Mix Moda Insights")
    window = MainWindow(resource_path("data/catalogo_produtos_estoque_geral.json"))
    window.show()
    sys.exit(app.exec())

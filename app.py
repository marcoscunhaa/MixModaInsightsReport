import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def resource_path(relative):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def persistent_data_directory():
    """Keep the user's alert rules beside the app, with a per-user fallback."""
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    preferred = base / "data"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_check"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return preferred
    except OSError:
        fallback = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        )
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Mix Moda")
    app.setApplicationName("Mix Moda Insights")
    window = MainWindow(
        resource_path("data/catalogo_produtos_estoque_geral.json"),
        persistent_data_directory(),
    )
    window.show()
    sys.exit(app.exec())

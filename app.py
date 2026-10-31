import sys
import threading
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from core.catalog_editor import (
    CatalogFileError, check_catalog, editable_catalog_path, recovery_sources, restore_catalog,
)
from ui.main_window import MainWindow
from ui.window_chrome import confirm_action, show_message


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


def ensure_valid_catalog(catalog_path, bundled_path):
    """Check the catalog before opening the app and offer to restore it if invalid.

    Returns True when the catalog can be used; False if the app should close.
    """
    try:
        check_catalog(catalog_path)
        return True
    except CatalogFileError as error:
        problem = str(error)
    close_splash()  # the splash screen would sit on top of the messages
    sources = recovery_sources(catalog_path, bundled_path)
    if not sources:
        show_message(
            None, "critical", "Invalid catalog",
            f"{problem}\n\nThere is no valid backup to restore. Fix the file at:\n{catalog_path}",
        )
        return False
    label, source = sources[0]
    if not confirm_action(
        None, "Invalid catalog",
        f"{problem}\n\nThe app can restore the {label}. The broken file is not "
        "deleted: it is kept in the same folder with a name containing \".corrupted\".",
        "Restore and open",
    ):
        return False
    try:
        kept = restore_catalog(catalog_path, source)
        check_catalog(catalog_path)
    except (OSError, CatalogFileError) as error:
        show_message(None, "critical", "Could not restore", str(error))
        return False
    show_message(
        None, "information", "Catalog restored",
        f"The catalog was restored from the {label}."
        + (f"\n\nThe broken file was kept at:\n{kept}" if kept else ""),
    )
    return True


def preload_heavy_modules():
    """Load pandas, charts and PDF in the background while the home screen is already open.

    Only modules without Qt windows: importing them creates no widgets, so it is safe
    outside the main thread. If the user generates an analysis before it finishes,
    Python waits for the in-progress import instead of repeating it.
    """
    def work():
        try:
            import pandas  # noqa: F401
            import core.loader  # noqa: F401
            import core.matcher  # noqa: F401
            import core.analyzer  # noqa: F401
            import matplotlib.figure  # noqa: F401
            import reportlab.platypus  # noqa: F401
            import openpyxl  # noqa: F401
            import rapidfuzz  # noqa: F401
        except Exception:
            pass  # without preloading, the app is only slower on the first analysis
    threading.Thread(target=work, name="preload", daemon=True).start()


def close_splash():
    """Close the executable's splash screen (it does not exist when running from source)."""
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Mix Moda")
    app.setApplicationName("Mix Moda Insights")
    data_dir = persistent_data_directory()
    # The JSON bundled in the .exe is read-only; stock edits go to the copy in the
    # data folder (when running from source, that is data/ itself).
    bundled_catalog = resource_path("data/catalogo_produtos_estoque_geral.json")
    catalog_path = editable_catalog_path(bundled_catalog, data_dir)
    if not ensure_valid_catalog(catalog_path, bundled_catalog):
        sys.exit(1)
    window = MainWindow(catalog_path, data_dir)
    window.show()
    close_splash()
    preload_heavy_modules()
    sys.exit(app.exec())

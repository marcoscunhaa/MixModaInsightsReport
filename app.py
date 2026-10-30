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
    """Confere o catálogo antes de abrir o app e oferece restaurar se estiver inválido.

    Devolve True quando o catálogo pode ser usado; False se o app deve fechar.
    """
    try:
        check_catalog(catalog_path)
        return True
    except CatalogFileError as error:
        problem = str(error)
    close_splash()  # a tela de abertura ficaria por cima das mensagens
    sources = recovery_sources(catalog_path, bundled_path)
    if not sources:
        show_message(
            None, "critical", "Catálogo inválido",
            f"{problem}\n\nNão há backup válido para restaurar. Corrija o arquivo em:\n{catalog_path}",
        )
        return False
    label, source = sources[0]
    if not confirm_action(
        None, "Catálogo inválido",
        f"{problem}\n\nO aplicativo pode restaurar o {label}. O arquivo com problema não é "
        "apagado: ele fica guardado na mesma pasta com o nome terminando em \".corrompido\".",
        "Restaurar e abrir",
    ):
        return False
    try:
        kept = restore_catalog(catalog_path, source)
        check_catalog(catalog_path)
    except (OSError, CatalogFileError) as error:
        show_message(None, "critical", "Não foi possível restaurar", str(error))
        return False
    show_message(
        None, "information", "Catálogo restaurado",
        f"O catálogo foi restaurado a partir do {label}."
        + (f"\n\nO arquivo com problema foi guardado em:\n{kept}" if kept else ""),
    )
    return True


def preload_heavy_modules():
    """Carrega pandas, gráficos e PDF em segundo plano enquanto a tela inicial já está aberta.

    Só módulos sem janelas Qt: importar não cria widgets, então é seguro fora da
    thread principal. Se o usuário gerar a análise antes de terminar, o Python
    espera o carregamento em andamento em vez de repetir.
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
            pass  # sem pré-carga o app só fica mais lento na primeira análise
    threading.Thread(target=work, name="preload", daemon=True).start()


def close_splash():
    """Fecha a tela de abertura do executável (não existe ao rodar pelo código-fonte)."""
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
    # O JSON embutido no .exe é somente leitura; as edições do estoque vão para a
    # cópia na pasta de dados (rodando pelo código-fonte é o próprio data/).
    bundled_catalog = resource_path("data/catalogo_produtos_estoque_geral.json")
    catalog_path = editable_catalog_path(bundled_catalog, data_dir)
    if not ensure_valid_catalog(catalog_path, bundled_catalog):
        sys.exit(1)
    window = MainWindow(catalog_path, data_dir)
    window.show()
    close_splash()
    preload_heavy_modules()
    sys.exit(app.exec())

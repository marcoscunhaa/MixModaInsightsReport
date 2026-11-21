"""Duas janelas do app abertas não podem apagar os cadastros uma da outra.

Cada janela guarda o catálogo do momento em que abriu. Antes, gravar essa cópia
apagava o que a outra janela tinha gravado depois (cadastros "sumiam" na análise
seguinte). Agora toda gravação relê o arquivo do disco antes de aplicar a mudança.
"""
import json
import shutil
from pathlib import Path

import pytest

from core import catalog_editor as ce
from core.catalog_store import load_catalog
from core.unclassified import apply_classifications

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalogo_produtos_estoque_geral.json"


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / CATALOG.name
    shutil.copy2(CATALOG, path)
    return path


def item(code, descricao, grupo):
    return {
        "codigo_barras": code, "descricao": descricao, "grupo": grupo, "subclasse": "SUB NOVA",
        "lojas": [{"loja": "Palmeiras", "descricao": descricao, "quantidade_catalogo": 2, "valor": 30}],
    }


def importar(window_catalog, path, items):
    """Mesmo caminho de ui/catalog_import.py: grava e troca o catálogo da janela."""
    fresh, summary = ce.commit_change(
        path, lambda c: apply_classifications(c, items), current=window_catalog,
        should_save=lambda s: s["cadastrados"] + s["atualizados"] > 0,
    )
    window_catalog.clear()
    window_catalog.update(fresh)
    return summary


def codes(path):
    return {p["codigo_barras"] for p in load_catalog(path)["produtos"]}


def test_two_windows_importing_keep_both_registrations(catalog_path):
    janela1 = load_catalog(catalog_path)
    janela2 = load_catalog(catalog_path)  # segundo clique no .exe
    importar(janela2, catalog_path, [item("7890000000017", "BLUSA ALFA", "GRUPO A"),
                                     item("7890000000024", "SHORT BETA", "GRUPO B")])
    importar(janela1, catalog_path, [item("7890000000048", "CHINELO DELTA", "GRUPO C")])
    assert {"7890000000017", "7890000000024", "7890000000048"} <= codes(catalog_path)
    # A janela que gravou por último também passa a mostrar o que a outra cadastrou.
    assert {p["codigo_barras"] for p in janela1["produtos"]} >= {"7890000000017", "7890000000048"}


def test_form_edit_in_stale_window_keeps_other_window_import(catalog_path):
    janela1 = load_catalog(catalog_path)
    janela2 = load_catalog(catalog_path)
    importar(janela2, catalog_path, [item("7890000000017", "BLUSA ALFA", "GRUPO A")])
    data = {**item("7890000000055", "CANECA EPSILON", "GRUPO D"), "situacao": "ATIVO"}
    fresh, _ = ce.commit_change(catalog_path, lambda c: ce.add_product(c, data), current=janela1)
    assert {"7890000000017", "7890000000055"} <= codes(catalog_path)
    assert {p["codigo_barras"] for p in fresh["produtos"]} == codes(catalog_path)


def test_failed_change_writes_nothing(catalog_path):
    before = catalog_path.read_bytes()

    def boom(catalog):
        catalog["produtos"].clear()
        raise ce.CatalogValidationError("dados inválidos")

    with pytest.raises(ce.CatalogValidationError):
        ce.commit_change(catalog_path, boom, current=load_catalog(catalog_path))
    assert catalog_path.read_bytes() == before


def test_nothing_to_save_does_not_touch_file(catalog_path):
    before = catalog_path.stat().st_mtime_ns
    _, summary = ce.commit_change(
        catalog_path, lambda c: apply_classifications(c, []), should_save=lambda s: s["cadastrados"] > 0,
    )
    assert summary["cadastrados"] == 0
    assert catalog_path.stat().st_mtime_ns == before
    assert not catalog_path.with_name(catalog_path.name + ".bak").exists()


def test_unreadable_file_falls_back_to_window_catalog(catalog_path):
    janela = load_catalog(catalog_path)
    catalog_path.write_text("{ quebrado", encoding="utf-8")
    data = {**item("7890000000062", "VASO ZETA", "GRUPO E"), "situacao": "ATIVO"}
    ce.commit_change(catalog_path, lambda c: ce.add_product(c, data), current=janela)
    saved = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert "7890000000062" in {p["codigo_barras"] for p in saved["produtos"]}
    assert len(saved["produtos"]) == len(janela["produtos"]) + 1

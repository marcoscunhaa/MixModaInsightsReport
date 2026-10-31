import json

import pytest

from core import catalog_editor as ce

GOOD = {"meta": {}, "produtos": [{"codigo_barras": "123", "descricao": "X", "lojas": []}]}


def write(path, content):
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_valid_catalog_passes(tmp_path):
    assert ce.check_catalog(write(tmp_path / "cat.json", GOOD)) == GOOD


@pytest.mark.parametrize("content, message", [
    ('{"produtos": [ {"codigo_barras": "1",, }', "invalid JSON"),
    ({"meta": {}}, "product list"),
    ({"produtos": [{"descricao": "no barcode", "lojas": []}]}, "Product #1"),
    ({"produtos": [{"codigo_barras": "1"}]}, "store list"),
])
def test_invalid_catalog_is_explained(tmp_path, content, message):
    with pytest.raises(ce.CatalogFileError, match=message):
        ce.check_catalog(write(tmp_path / "cat.json", content))


def test_missing_catalog(tmp_path):
    with pytest.raises(ce.CatalogFileError, match="was not found"):
        ce.check_catalog(tmp_path / "nada.json")


def test_recovery_prefers_valid_backup_then_bundled(tmp_path):
    cat = write(tmp_path / "cat.json", "{broken")
    bundled = write(tmp_path / "bundle.json", GOOD)
    write(tmp_path / "cat.json.bak", GOOD)
    assert [label for label, _ in ce.recovery_sources(cat, bundled)] == [
        "backup of the last change", "original catalog bundled with the app"]
    write(tmp_path / "cat.json.bak", "{also broken")
    assert [src for _, src in ce.recovery_sources(cat, bundled)] == [bundled]
    assert ce.recovery_sources(cat, cat) == []          # running from source: no separate bundled catalog


def test_restore_keeps_broken_file(tmp_path):
    cat = write(tmp_path / "cat.json", "{broken")
    backup = write(tmp_path / "cat.json.bak", GOOD)
    kept = ce.restore_catalog(cat, backup)
    assert ce.check_catalog(cat) == GOOD
    assert kept.read_text(encoding="utf-8") == "{broken"
    assert kept.name.startswith("cat.corrupted-") and kept.suffix == ".json"

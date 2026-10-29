import copy
import json
from pathlib import Path

import pytest

from core import catalog_editor as ce

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalogo_produtos_estoque_geral.json"


@pytest.fixture(scope="module")
def original_text():
    return CATALOG.read_text(encoding="utf-8")


@pytest.fixture
def catalog(original_text):
    return json.loads(original_text)


def form_data(product):
    """O que o formulário devolve ao abrir e salvar um produto sem mexer em nada."""
    return {
        "codigo_barras": product["codigo_barras"],
        "descricao": product["descricao"],
        "grupo": product["grupo"],
        "subclasse": product["subclasse"],
        "situacao": product["situacao"],
        "lojas": [
            {
                "loja": l["loja"],
                "descricao": l["descricao"],
                "quantidade_catalogo": l["quantidade_catalogo"],
                "valor": l["valor"],
            }
            for l in product["lojas"]
        ],
    }


def test_saving_unchanged_products_keeps_file_identical(catalog, original_text, tmp_path):
    for product in list(catalog["produtos"]):
        ce.update_product(catalog, product["codigo_barras"], form_data(product))
    out = tmp_path / "catalogo.json"
    ce.save_catalog(catalog, out, keep_backup=False)
    assert out.read_text(encoding="utf-8") == original_text


def test_refresh_meta_matches_generated_totals(catalog):
    before = copy.deepcopy(catalog["meta"])
    ce.refresh_meta(catalog)
    assert catalog["meta"] == before


def test_add_product(catalog):
    total = len(catalog["produtos"])
    product = ce.add_product(catalog, {
        "codigo_barras": "0099887766",
        "descricao": "  BLUSA   TESTE  ",
        "grupo": "VESTUARIO FEMININO",
        "subclasse": "BLUSA",
        "lojas": [{"loja": "Palmeiras", "quantidade_catalogo": 3, "valor": "19,9"}],
    })
    assert len(catalog["produtos"]) == total + 1
    assert product["descricao"] == "BLUSA TESTE"
    assert product["situacao"] == "ATIVO"
    store = product["lojas"][0]
    assert store["codigo_barras"] == "99887766"
    assert store["descricao_norm"] == "BLUSA TESTE"
    assert (store["quantidade_catalogo"], store["valor"]) == ("3", "19.90")
    assert catalog["meta"]["total_produtos_unicos_por_codigo"] == total + 1
    assert catalog["meta"]["total_linhas"] == 6122


def test_negative_quantity_allowed_negative_price_rejected(catalog):
    data = form_data(catalog["produtos"][0])
    data["lojas"][0]["quantidade_catalogo"] = -2
    product = ce.update_product(catalog, data["codigo_barras"], data)
    assert product["lojas"][0]["quantidade_catalogo"] == "-2"
    data["lojas"][0]["valor"] = -1
    with pytest.raises(ce.CatalogValidationError, match="negativo"):
        ce.update_product(catalog, data["codigo_barras"], data)


def test_cannot_change_code_into_another_products_number(catalog):
    data = form_data(catalog["produtos"][1])
    original = data["codigo_barras"]
    data["codigo_barras"] = "40141247193"
    with pytest.raises(ce.CatalogValidationError, match="Já existe"):
        ce.update_product(catalog, original, data)


def test_add_rejects_duplicate_code_even_with_leading_zeros(catalog):
    existing = catalog["produtos"][0]["codigo_barras"]  # 0040141247193
    with pytest.raises(ce.CatalogValidationError):
        ce.add_product(catalog, {
            **form_data(catalog["produtos"][0]),
            "codigo_barras": existing.lstrip("0"),
        })


@pytest.mark.parametrize("patch, message", [
    ({"codigo_barras": ""}, "código"),
    ({"codigo_barras": "12A4"}, "números"),
    ({"descricao": " "}, "descrição"),
    ({"grupo": ""}, "grupo"),
    ({"lojas": []}, "pelo menos uma loja"),
])
def test_validation(catalog, patch, message):
    data = {**form_data(catalog["produtos"][0]), "codigo_barras": "123456", **patch}
    with pytest.raises(ce.CatalogValidationError, match=message):
        ce.add_product(catalog, data)


def test_duplicate_store_rejected(catalog):
    data = form_data(catalog["produtos"][0])
    data["lojas"] = data["lojas"] * 2
    with pytest.raises(ce.CatalogValidationError, match="mais de uma vez"):
        ce.update_product(catalog, data["codigo_barras"], data)


def test_update_propagates_description_but_keeps_store_specific_one(catalog):
    product = next(p for p in catalog["produtos"]
                   if any(l["descricao"] != p["descricao"] for l in p["lojas"])
                   and any(l["descricao"] == p["descricao"] for l in p["lojas"]))
    data = form_data(product)
    data["descricao"] = "NOVA DESCRICAO"
    data["grupo"] = "UTILIDADES"
    updated = ce.update_product(catalog, product["codigo_barras"], data)
    for old, new in zip(product["lojas"], updated["lojas"]):
        expected = "NOVA DESCRICAO" if old["descricao"] == product["descricao"] else old["descricao"]
        assert new["descricao"] == expected
        assert new["grupo"] == "UTILIDADES"


def test_update_can_change_code_and_store_values(catalog):
    product = catalog["produtos"][0]
    data = form_data(product)
    data["codigo_barras"] = "7000000000001"
    data["lojas"][0]["quantidade_catalogo"] = 40
    ce.update_product(catalog, product["codigo_barras"], data)
    assert ce.find_product(catalog, "0040141247193") is None
    updated = ce.find_product(catalog, "7000000000001")
    assert updated["lojas"][0]["quantidade_catalogo"] == "40"
    assert updated["lojas"][0]["valor"] == product["lojas"][0]["valor"]


def test_delete_product(catalog):
    total = len(catalog["produtos"])
    ce.delete_product(catalog, "0040141247193")
    assert len(catalog["produtos"]) == total - 1
    assert ce.find_product(catalog, "0040141247193") is None
    # o par legado com o mesmo número (sem um zero) continua lá
    assert ce.find_product(catalog, "040141247193") is not None
    with pytest.raises(ce.CatalogValidationError):
        ce.delete_product(catalog, "0040141247193")


def test_save_keeps_backup(catalog, original_text, tmp_path):
    out = tmp_path / "catalogo.json"
    out.write_text(original_text, encoding="utf-8")
    ce.delete_product(catalog, "0040141247193")
    ce.save_catalog(catalog, out)
    assert (tmp_path / "catalogo.json.bak").read_text(encoding="utf-8") == original_text
    assert json.loads(out.read_text(encoding="utf-8"))["meta"]["total_produtos_unicos_por_codigo"] == 2162


def test_editable_catalog_path(tmp_path):
    bundled = tmp_path / "bundle" / "catalogo.json"
    bundled.parent.mkdir()
    bundled.write_text("{}", encoding="utf-8")
    assert ce.editable_catalog_path(bundled, bundled.parent) == bundled
    target = ce.editable_catalog_path(bundled, tmp_path / "user")
    assert target == tmp_path / "user" / "catalogo.json" and target.read_text() == "{}"
    target.write_text('{"x": 1}')
    assert ce.editable_catalog_path(bundled, tmp_path / "user").read_text() == '{"x": 1}'

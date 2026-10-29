"""CRUD do catálogo oficial (catalogo_produtos_estoque_geral.json).

Cada produto tem dados gerais (código, descrição, grupo, subclasse, situação) e
uma lista `lojas[]` com quantidade, valor e a descrição usada naquela loja. O
cruzamento com as vendas usa loja + código + descrição, então a descrição de
cada loja é preservada quando difere da descrição geral.

Este módulo não depende de Qt: a tela de estoque só chama estas funções.
"""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from core.stores import STORES
from utils.normalization import normalize_barcode, normalize_text

SITUACOES = ("ATIVO", "DESATIVADO")


class CatalogValidationError(ValueError):
    """Dados do formulário inválidos; a mensagem é exibida ao usuário."""


def clean_label(value):
    """Remove espaços extras. A caixa alta é aplicada pelo formulário ao digitar,
    para não reescrever textos legados que o usuário não alterou."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_number(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def format_quantity(value):
    return str(int(round(parse_number(value))))


def format_price(value):
    return f"{parse_number(value):.2f}"


def product_stock(product):
    return sum(parse_number(l.get("quantidade_catalogo")) for l in product.get("lojas", []))


def store_names(catalog):
    """Lojas da rede (core.stores), com a grafia já usada no catálogo.

    O catálogo grava "pedras" em minúsculo; reaproveitar a grafia existente evita
    duas versões da mesma loja no JSON. Lojas que só existem no catálogo vêm no fim.
    """
    in_catalog = list(catalog.get("meta", {}).get("lojas", []))
    for product in catalog.get("produtos", []):
        for entry in product.get("lojas", []):
            in_catalog.append(entry.get("loja", ""))
    spelling = {}
    for name in in_catalog:
        if name:
            spelling.setdefault(normalize_text(name), name)
    names = [spelling.get(normalize_text(store), store) for store in STORES]
    official = {normalize_text(store) for store in STORES}
    names += [name for key, name in spelling.items() if key not in official]
    return names


def groups_and_subclasses(catalog):
    """{grupo: [subclasses]} ordenado, para preencher os combos do formulário."""
    tree = {}
    for product in catalog.get("produtos", []):
        tree.setdefault(product.get("grupo", ""), set()).add(product.get("subclasse", ""))
    return {
        g: sorted((s for s in subs if s), key=normalize_text)
        for g, subs in sorted(tree.items(), key=lambda kv: normalize_text(kv[0]))
        if g
    }


def find_product(catalog, codigo_barras):
    """Busca pelo código exato: o catálogo legado tem pares que só diferem por zeros à esquerda."""
    code = str(codigo_barras).strip()
    for product in catalog.get("produtos", []):
        if str(product.get("codigo_barras")).strip() == code:
            return product
    return None


def _same_code_product(catalog, code, ignore=None):
    """Outro produto cujo código é o mesmo número (ignorando zeros à esquerda)."""
    key = normalize_barcode(code)
    for product in catalog.get("produtos", []):
        if product is not ignore and normalize_barcode(product.get("codigo_barras")) == key:
            return product
    return None


def _validate(catalog, data, original_code=None):
    code = re.sub(r"\s+", "", str(data.get("codigo_barras", "")))
    if not code:
        raise CatalogValidationError("Informe o código de barras.")
    if not code.isdigit():
        raise CatalogValidationError("O código de barras deve conter apenas números.")
    descricao = clean_label(data.get("descricao"))
    grupo = clean_label(data.get("grupo"))
    subclasse = clean_label(data.get("subclasse"))
    situacao = clean_label(data.get("situacao") or "ATIVO").upper()
    if not descricao:
        raise CatalogValidationError("Informe a descrição do produto.")
    if not grupo:
        raise CatalogValidationError("Informe o grupo.")
    if not subclasse:
        raise CatalogValidationError("Informe a subclasse.")
    if situacao not in SITUACOES:
        raise CatalogValidationError("Situação deve ser ATIVO ou DESATIVADO.")

    original = find_product(catalog, original_code) if original_code is not None else None
    changed_number = original is None or normalize_barcode(code) != normalize_barcode(original_code)
    existing = _same_code_product(catalog, code, ignore=original) if changed_number else None
    if existing is not None:
        raise CatalogValidationError(
            f"Já existe um produto com o código {existing['codigo_barras']}: {existing['descricao']}."
        )

    lojas = []
    seen = set()
    for entry in data.get("lojas", []):
        loja = str(entry.get("loja", "")).strip()
        if not loja:
            raise CatalogValidationError("Selecione a loja em todas as linhas.")
        if normalize_text(loja) in seen:
            raise CatalogValidationError(f"A loja {loja} aparece mais de uma vez.")
        seen.add(normalize_text(loja))
        quantidade = parse_number(entry.get("quantidade_catalogo"))
        valor = parse_number(entry.get("valor"))
        # Quantidade negativa existe no estoque real (venda sem entrada); preço não.
        if valor < 0:
            raise CatalogValidationError(f"O valor não pode ser negativo ({loja}).")
        lojas.append({
            "loja": loja,
            "descricao": clean_label(entry.get("descricao")) or descricao,
            "quantidade_catalogo": quantidade,
            "valor": valor,
        })
    if not lojas:
        raise CatalogValidationError("Marque pelo menos uma loja.")
    return {
        "codigo_barras": code,
        "descricao": descricao,
        "grupo": grupo,
        "subclasse": subclasse,
        "situacao": situacao,
        "lojas": lojas,
    }


def _store_entry(clean, store, previous=None):
    """Monta lojas[] na mesma ordem de chaves do arquivo original.

    Quantidade e valor numericamente iguais mantêm o texto anterior, para que o
    diff do JSON mostre só o que realmente mudou.
    """
    previous = previous or {}
    qty = previous.get("quantidade_catalogo")
    if qty is None or parse_number(qty) != store["quantidade_catalogo"]:
        qty = format_quantity(store["quantidade_catalogo"])
    price = previous.get("valor")
    if price is None or round(parse_number(price), 2) != round(store["valor"], 2):
        price = format_price(store["valor"])
    return {
        "loja": store["loja"],
        "situacao": clean["situacao"],
        "grupo": clean["grupo"],
        "subclasse": clean["subclasse"],
        "descricao": store["descricao"],
        "quantidade_catalogo": qty,
        "valor": price,
        "codigo_barras": normalize_barcode(clean["codigo_barras"]),
        "descricao_norm": normalize_text(store["descricao"]),
    }


def _build_product(clean, previous=None):
    old_stores = {normalize_text(l["loja"]): l for l in (previous or {}).get("lojas", [])}
    return {
        "codigo_barras": clean["codigo_barras"],
        "grupo": clean["grupo"],
        "subclasse": clean["subclasse"],
        "descricao": clean["descricao"],
        "situacao": clean["situacao"],
        "lojas": [
            _store_entry(clean, store, old_stores.get(normalize_text(store["loja"])))
            for store in clean["lojas"]
        ],
    }


def refresh_meta(catalog):
    """Recalcula os totais do meta com as mesmas regras do arquivo gerado."""
    products = catalog.get("produtos", [])
    entries = [l for p in products for l in p.get("lojas", [])]
    meta = catalog.setdefault("meta", {})
    meta["total_linhas"] = len(entries)
    meta["total_produtos_unicos_por_codigo"] = len(products)
    meta["total_grupos"] = len({p.get("grupo") for p in products})
    meta["total_subclasses"] = len({p.get("subclasse") for p in products})
    lojas = list(meta.get("lojas", []))
    known = {normalize_text(n) for n in lojas}
    for entry in entries:
        if normalize_text(entry.get("loja")) not in known:
            known.add(normalize_text(entry.get("loja")))
            lojas.append(entry.get("loja"))
    meta["lojas"] = lojas
    classificacao = meta.setdefault("classificacao", {})
    classificacao["total_registros"] = len(entries)
    classificacao["total_grupos"] = len({l.get("grupo") for l in entries})
    classificacao["total_subclasses"] = len({(l.get("grupo"), l.get("subclasse")) for l in entries})
    return catalog


def add_product(catalog, data):
    clean = _validate(catalog, data)
    product = _build_product(clean)
    catalog.setdefault("produtos", []).append(product)
    refresh_meta(catalog)
    return product


def update_product(catalog, original_code, data):
    products = catalog.get("produtos", [])
    previous = find_product(catalog, original_code)
    if previous is None:
        raise CatalogValidationError("Produto não encontrado; ele pode ter sido removido.")
    clean = _validate(catalog, data, original_code=original_code)
    index = next(i for i, p in enumerate(products) if p is previous)
    # Lojas cuja descrição acompanhava a descrição geral seguem a nova descrição.
    old_description = normalize_text(previous.get("descricao"))
    if normalize_text(clean["descricao"]) != old_description:
        for store in clean["lojas"]:
            if normalize_text(store["descricao"]) == old_description:
                store["descricao"] = clean["descricao"]
    products[index] = _build_product(clean, previous)
    refresh_meta(catalog)
    return products[index]


def delete_product(catalog, codigo_barras):
    products = catalog.get("produtos", [])
    target = find_product(catalog, codigo_barras)
    remaining = [p for p in products if p is not target]
    if target is None:
        raise CatalogValidationError("Produto não encontrado; ele pode já ter sido removido.")
    catalog["produtos"] = remaining
    refresh_meta(catalog)


def save_catalog(catalog, path, keep_backup=True):
    """Grava de forma atômica, no mesmo formato do arquivo (indent 2, UTF-8).

    A versão anterior fica em `<arquivo>.bak` para desfazer um erro manualmente.
    """
    path = Path(path)
    payload = json.dumps(catalog, ensure_ascii=False, indent=2)
    if keep_backup and path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".catalogo-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def editable_catalog_path(bundled_path, data_dir):
    """Caminho gravável do catálogo.

    Rodando pelo código-fonte, o catálogo já fica em data/ e é editado no lugar.
    No executável, o JSON embutido é somente leitura: na primeira execução ele é
    copiado para a pasta de dados do usuário e as edições vão para essa cópia.
    """
    bundled = Path(bundled_path)
    target = Path(data_dir) / bundled.name
    if target.resolve() == bundled.resolve():
        return bundled
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)
    return target


# ---------- catálogo corrompido ----------

class CatalogFileError(ValueError):
    """O arquivo do catálogo não pode ser usado; a mensagem explica o motivo."""


def check_catalog(path):
    """Lê e valida a estrutura mínima do catálogo. Devolve o catálogo ou levanta CatalogFileError."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            catalog = json.load(f)
    except FileNotFoundError:
        raise CatalogFileError(f"O arquivo {path.name} não foi encontrado.") from None
    except json.JSONDecodeError as error:
        raise CatalogFileError(
            f"O arquivo {path.name} está com o formato JSON inválido "
            f"(linha {error.lineno}, coluna {error.colno}: {error.msg})."
        ) from None
    except (OSError, UnicodeDecodeError) as error:
        raise CatalogFileError(f"Não foi possível ler {path.name}: {error}") from None
    if not isinstance(catalog, dict) or not isinstance(catalog.get("produtos"), list):
        raise CatalogFileError(f"O arquivo {path.name} não tem a lista de produtos do catálogo.")
    for index, product in enumerate(catalog["produtos"], start=1):
        if (
            not isinstance(product, dict)
            or not str(product.get("codigo_barras", "")).strip()
            or not isinstance(product.get("lojas"), list)
        ):
            raise CatalogFileError(
                f"O produto nº {index} do arquivo {path.name} está incompleto "
                "(sem código de barras ou sem a lista de lojas)."
            )
    return catalog


def recovery_sources(path, bundled_path=None):
    """Cópias válidas para restaurar, na ordem de preferência: backup e catálogo embutido."""
    path = Path(path)
    options = [("backup da última alteração", path.with_name(path.name + ".bak"))]
    if bundled_path and Path(bundled_path).resolve() != path.resolve():
        options.append(("catálogo original do aplicativo", Path(bundled_path)))
    valid = []
    for label, source in options:
        try:
            check_catalog(source)
        except CatalogFileError:
            continue
        valid.append((label, source))
    return valid


def restore_catalog(path, source):
    """Troca o catálogo inválido pela cópia `source`, guardando o arquivo inválido.

    O arquivo com problema nunca é apagado: vira `<nome>.corrompido-<data-hora>.json`
    na mesma pasta, para conferência. Devolve o caminho onde ele foi guardado.
    """
    from datetime import datetime

    path = Path(path)
    kept = None
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        kept = path.with_name(f"{path.stem}.corrompido-{stamp}{path.suffix}")
        shutil.copy2(path, kept)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".catalogo-", suffix=".json")
    os.close(fd)
    try:
        shutil.copy2(source, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return kept

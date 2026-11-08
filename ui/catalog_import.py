"""Importar cadastro: lê um Excel e grava grupo/subclasse no catálogo.

Usado pelo botão "Importar planilha de classificação" do Explorar estoque. Aceita o Excel
de produtos sem classificação gerado pelo app ou uma planilha com colunas
equivalentes (código, descrição, grupo, subclasse, loja, estoque, preço).
"""
import copy

from core import catalog_editor as ce
from ui.window_chrome import confirm_action, get_open_file, show_message
from utils.formatting import br_number
from utils.normalization import normalize_barcode


def import_catalog_excel(parent, catalog, catalog_path, on_changed=None):
    """Fluxo completo com diálogos. Retorna True quando o catálogo foi gravado."""
    from core.unclassified import apply_classifications
    from exports.unclassified_export import ClassificationFileError, read_classification_xlsx

    path = get_open_file(parent, "Importar cadastro (Excel)", "Excel (*.xlsx *.xlsm)")
    if not path:
        return False
    try:
        items, warnings = read_classification_xlsx(path)
    except ClassificationFileError as error:
        show_message(parent, "warning", "Arquivo não reconhecido", str(error))
        return False
    except Exception as error:
        show_message(parent, "critical", "Não foi possível ler o Excel", f"{type(error).__name__}: {error}")
        return False
    if not items:
        extra = "\n\n" + "\n".join(warnings[:10]) if warnings else ""
        show_message(parent, "information", "Nada para importar",
                     "Nenhuma linha com GRUPO e SUBCLASSE preenchidos." + extra)
        return False

    known = {normalize_barcode(p.get("codigo_barras")) for p in catalog.get("produtos", [])}
    updates = sum(normalize_barcode(i["codigo_barras"]) in known for i in items)
    stores = {e["loja"] for i in items for e in i["lojas"]}
    if not confirm_action(
        parent, "Importar cadastro",
        f"{br_number(len(items), 0)} produto(s) no arquivo: {br_number(len(items) - updates, 0)} novo(s) "
        f"e {br_number(updates, 0)} já no catálogo (a classificação será atualizada), "
        f"em {br_number(len(stores), 0)} loja(s).",
        "Importar",
    ):
        return False

    # Grava numa cópia: se salvar falhar, o catálogo em uso fica como estava.
    candidate = copy.deepcopy(catalog)
    summary = apply_classifications(candidate, items)
    saved = summary["cadastrados"] + summary["atualizados"] > 0
    if saved:
        try:
            ce.save_catalog(candidate, catalog_path)
        except Exception as error:
            show_message(parent, "critical", "Não foi possível salvar o catálogo", f"{type(error).__name__}: {error}")
            return False
        catalog.clear()
        catalog.update(candidate)
        if on_changed:
            on_changed()

    lines = [f"{br_number(summary['cadastrados'], 0)} produto(s) cadastrados e "
             f"{br_number(summary['atualizados'], 0)} atualizados."]
    problems = summary["erros"] + warnings
    if problems:
        lines.append(f"\n{len(problems)} produto(s) ficaram de fora:")
        lines += problems[:12] + ([f"… e mais {len(problems) - 12}"] if len(problems) > 12 else [])
    if saved:
        lines.append("\nO dashboard e a última análise já mostram a classificação nova.")
    show_message(parent, "warning" if problems else "information", "Cadastro importado", "\n".join(lines))
    return saved

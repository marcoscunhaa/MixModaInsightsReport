import pandas as pd
from utils.normalization import normalize_barcode, normalize_text
from core.cleaner import clean_dataframe


def load_classification(path):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classification_frame(reference):
    rows = []
    for p in reference.get("produtos", []):
        rows.append({
            "loja_ref": str(p.get("loja", "")).strip(),
            "codigo_barras": normalize_barcode(p.get("codigo_barras")),
            "descricao_norm": normalize_text(p.get("descricao_norm") or p.get("descricao", "")),
            "grupo_ref": p.get("grupo", ""),
            "subclasse_ref": p.get("subclasse", ""),
            "situacao_ref": p.get("situacao", ""),
        })
    columns = ["loja_ref", "codigo_barras", "descricao_norm", "grupo_ref", "subclasse_ref", "situacao_ref"]
    return pd.DataFrame(rows, columns=columns).drop_duplicates(["loja_ref", "codigo_barras", "descricao_norm"])


def catalog_classification_frame(catalog):
    """Build the store-independent classification master from the JSON catalog."""
    rows = []
    for product in (catalog or {}).get("produtos", []):
        rows.append({
            "codigo_barras": normalize_barcode(product.get("codigo_barras")),
            "descricao_norm": normalize_text(product.get("descricao_norm") or product.get("descricao", "")),
            "grupo_ref": product.get("grupo", ""),
            "subclasse_ref": product.get("subclasse", ""),
        })
    return pd.DataFrame(rows).drop_duplicates()


def _unique_classification(frame, key):
    """Keep keys whose catalog rows agree on one non-empty group/subclass pair."""
    frame = frame[(frame.grupo_ref.fillna("").astype(str).str.strip() != "") &
                  (frame.subclasse_ref.fillna("").astype(str).str.strip() != "")].copy()
    if frame.empty:
        return frame[[key, "grupo_ref", "subclasse_ref"]]
    counts = frame.groupby(key)[["grupo_ref", "subclasse_ref"]].nunique(dropna=False)
    keys = counts[(counts.grupo_ref == 1) & (counts.subclasse_ref == 1)].index
    return frame[frame[key].isin(keys)].drop_duplicates(key)[[key, "grupo_ref", "subclasse_ref"]]


def build_analysis(df_estoque, df_vendas, catalog, loja, config, classification=None):
    estoque, ig1 = clean_dataframe(df_estoque)
    vendas, ig2 = clean_dataframe(df_vendas)
    for d in (estoque, vendas):
        d["codigo_barras"] = d["codigo_barras"].map(normalize_barcode)
        d["descricao_norm"] = d["descricao"].map(normalize_text)
    estoque = estoque[estoque.codigo_barras != ""].copy()
    vendas = vendas[vendas.codigo_barras != ""].copy()

    # Consolida linhas duplicadas do mesmo produto no estoque antes do cruzamento.
    # Isso evita multiplicar as vendas quando o mesmo código + descrição aparece
    # mais de uma vez na extração. O preço de compra é média ponderada pela quantidade.
    estoque["_valor_compra_total"] = estoque["quantidade_estoque"] * estoque["preco_compra"]
    stock_group = estoque.groupby(["codigo_barras", "descricao_norm"], as_index=False).agg(
        descricao=("descricao", "first"),
        quantidade_estoque=("quantidade_estoque", "sum"),
        _valor_compra_total=("_valor_compra_total", "sum"),
        preco_compra_fallback=("preco_compra", "mean"),
    )
    stock_group["preco_compra"] = stock_group.apply(
        lambda r: r["_valor_compra_total"] / r["quantidade_estoque"]
        if r["quantidade_estoque"] else r["preco_compra_fallback"], axis=1
    )
    estoque = stock_group.drop(columns=["_valor_compra_total", "preco_compra_fallback"])

    # Vendas só entram quando código + descrição existem no estoque da mesma loja.
    vs = vendas.groupby(["codigo_barras", "descricao_norm"], as_index=False)["quantidade_vendida"].sum()
    merged = estoque.merge(vs, on=["codigo_barras", "descricao_norm"], how="left")
    merged["quantidade_vendida"] = merged["quantidade_vendida"].fillna(0)
    merged["loja"] = loja

    # Classificação específica da loja tem prioridade quando existir.
    if classification:
        cf = classification_frame(classification)
        cf = cf[cf.loja_ref.map(normalize_text) == normalize_text(loja)].copy()
        merged = merged.merge(cf, on=["codigo_barras", "descricao_norm"], how="left")
    else:
        merged["grupo_ref"] = None
        merged["subclasse_ref"] = None

    # Primeiro tenta o código da loja selecionada, se ele tiver classificação única.
    if classification:
        cf2 = classification_frame(classification)
        cf2 = cf2[cf2.loja_ref.map(normalize_text) == normalize_text(loja)].copy()
        unique_code = _unique_classification(cf2, "codigo_barras")
        merged = merged.merge(unique_code, on="codigo_barras", how="left", suffixes=("", "_fallback"))
        merged["grupo_ref"] = merged["grupo_ref"].fillna(merged["grupo_ref_fallback"])
        merged["subclasse_ref"] = merged["subclasse_ref"].fillna(merged["subclasse_ref_fallback"])
        merged.drop(columns=[c for c in ["grupo_ref_fallback", "subclasse_ref_fallback"] if c in merged.columns], inplace=True)

    # The JSON's top-level product record is the global master. Use it regardless
    # of selected store, then a globally unique description for codes absent there.
    global_catalog = catalog_classification_frame(catalog)
    if not global_catalog.empty:
        # The source JSON has one known barcode collision: two zero-padded
        # codes both describe LENÇOL CASAL BASICO, but one is wrongly tagged as
        # a skirt. Keep this explicit correction until the upstream catalog is fixed.
        linen = global_catalog.descricao_norm == normalize_text("LENÇOL CASAL BASICO")
        global_catalog.loc[linen, ["grupo_ref", "subclasse_ref"]] = ["UTILIDADES", "COLCHA"]
        global_code = _unique_classification(global_catalog, "codigo_barras")
        merged = merged.merge(global_code, on="codigo_barras", how="left", suffixes=("", "_global_code"))
        # A unique global classification is authoritative, so choosing a
        # different store cannot change the product's group or subclass.
        merged["grupo_ref"] = merged["grupo_ref_global_code"].fillna(merged["grupo_ref"])
        merged["subclasse_ref"] = merged["subclasse_ref_global_code"].fillna(merged["subclasse_ref"])
        merged.drop(columns=["grupo_ref_global_code", "subclasse_ref_global_code"], inplace=True)

        global_description = _unique_classification(global_catalog, "descricao_norm")
        merged = merged.merge(global_description, on="descricao_norm", how="left", suffixes=("", "_global_description"))
        merged["grupo_ref"] = merged["grupo_ref"].fillna(merged["grupo_ref_global_description"])
        merged["subclasse_ref"] = merged["subclasse_ref"].fillna(merged["subclasse_ref_global_description"])
        merged.drop(columns=["grupo_ref_global_description", "subclasse_ref_global_description"], inplace=True)

    # Override a known source inconsistency even when the selected store carries
    # the wrong local tag for this globally identifiable product.
    linen = merged.descricao_norm == normalize_text("LENÇOL CASAL BASICO")
    merged.loc[linen, ["grupo_ref", "subclasse_ref"]] = ["UTILIDADES", "COLCHA"]

    merged["grupo"] = merged["grupo_ref"].fillna("SEM CLASSIFICAÇÃO")
    merged["subclasse"] = merged["subclasse_ref"].fillna("SEM CLASSIFICAÇÃO")

    stock_keys = set(zip(estoque.codigo_barras, estoque.descricao_norm))
    sales_keys = set(zip(vendas.codigo_barras, vendas.descricao_norm))

    # Regra comercial da Mix Moda: preço de venda = 2x preço de compra.
    merged["preco_compra"] = pd.to_numeric(merged["preco_compra"], errors="coerce").fillna(0)
    merged["preco_venda"] = merged["preco_compra"] * 2
    merged["valor_estoque"] = merged.quantidade_estoque * merged.preco_compra
    merged["valor_vendido"] = merged.quantidade_vendida * merged.preco_venda
    merged["margem_unitaria"] = merged.preco_venda - merged.preco_compra
    merged["margem_percentual"] = merged.apply(lambda r: r.margem_unitaria / r.preco_venda * 100 if r.preco_venda else 0, axis=1)
    # Com os arquivos disponíveis temos vendas do período + estoque final, mas não
    # temos estoque inicial/entradas. Portanto não é matematicamente correto chamar
    # vendas/estoque-final de "turnover" (isso pode explodir quando o estoque é 1).
    # Usamos uma taxa de giro/sell-through do período, limitada a 0–100%:
    # vendas / (vendas + estoque final).
    merged["giro"] = merged.apply(
        lambda r: (r.quantidade_vendida / (r.quantidade_vendida + r.quantidade_estoque) * 100)
        if (r.quantidade_vendida + r.quantidade_estoque) > 0 else 0, axis=1
    )
    merged["cobertura"] = merged.apply(lambda r: r.quantidade_estoque / r.quantidade_vendida if r.quantidade_vendida > 0 else float("inf"), axis=1)
    merged["produto_sem_venda"] = merged.quantidade_vendida <= 0
    merged["ruptura"] = (merged.quantidade_estoque <= 0) & (merged.quantidade_vendida > 0)
    merged["risco_ruptura"] = (merged.cobertura <= config.cobertura_risco) & (merged.quantidade_vendida > 0)

    def status(r):
        q, v = r.quantidade_estoque, r.quantidade_vendida
        if q <= 0 and v > 0: return "SEM ESTOQUE"
        if q <= config.estoque_critico: return "CRÍTICO"
        if q <= config.estoque_baixo: return "BAIXO"
        if v <= 0: return "SEM VENDA"
        if r.cobertura >= config.excesso_cobertura: return "EXCESSO"
        return "NORMAL"
    merged["status_estoque"] = merged.apply(status, axis=1)

    audit = {
        "produtos_estoque": len(estoque), "produtos_vendas": len(vendas),
        "vendas_correspondentes": len(sales_keys & stock_keys), "vendas_sem_correspondencia": len(sales_keys - stock_keys),
        "produtos_ignorados": ig1 + ig2, "codigos_invalidos": int((df_estoque.codigo_barras.map(normalize_barcode) == "").sum()),
        "descricoes_divergentes": len(sales_keys - stock_keys),
        "produtos_sem_classificacao": int((merged.grupo == "SEM CLASSIFICAÇÃO").sum()),
    }
    return merged, audit

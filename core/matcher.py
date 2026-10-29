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
    if "preco_venda" not in estoque:
        estoque["preco_venda"] = 0.0
    estoque["preco_venda"] = pd.to_numeric(estoque["preco_venda"], errors="coerce").fillna(0)
    estoque["_valor_compra_total"] = estoque["quantidade_estoque"] * estoque["preco_compra"]
    stock_group = estoque.groupby(["codigo_barras", "descricao_norm"], as_index=False).agg(
        descricao=("descricao", "first"),
        quantidade_estoque=("quantidade_estoque", "sum"),
        _valor_compra_total=("_valor_compra_total", "sum"),
        preco_compra_fallback=("preco_compra", "mean"),
        preco_venda_estoque=("preco_venda", "max"),
    )
    stock_group["preco_compra"] = stock_group.apply(
        lambda r: r["_valor_compra_total"] / r["quantidade_estoque"]
        if r["quantidade_estoque"] else r["preco_compra_fallback"], axis=1
    )
    estoque = stock_group.drop(columns=["_valor_compra_total", "preco_compra_fallback"])

    # O estoque fornece a descrição atual. Para códigos únicos no estoque, vendas
    # com descrições antigas são associadas ao produto pelo código de barras.
    # Se um código aparecer com mais de uma descrição atual, mantém-se a descrição
    # como desempate para evitar duplicar as vendas entre produtos ambíguos.
    stock_desc_counts = estoque.groupby("codigo_barras")["descricao_norm"].nunique()
    unique_stock_codes = set(stock_desc_counts[stock_desc_counts == 1].index)
    current_description = (
        estoque[estoque.codigo_barras.isin(unique_stock_codes)]
        .drop_duplicates("codigo_barras")
        .set_index("codigo_barras")["descricao_norm"]
    )
    vendas["_descricao_match"] = vendas["descricao_norm"]
    unique_code_mask = vendas["codigo_barras"].isin(unique_stock_codes)
    vendas.loc[unique_code_mask, "_descricao_match"] = (
        vendas.loc[unique_code_mask, "codigo_barras"].map(current_description)
    )
    # Planilha de vendas: C quantidade, D preço de compra, F preço de venda,
    # G faturamento. O mesmo produto pode vir em várias linhas com preços
    # diferentes; somamos faturamento e custo e o preço vira a média ponderada.
    for column in ("preco_compra", "preco_venda", "faturamento"):
        if column not in vendas:
            vendas[column] = 0.0
        vendas[column] = pd.to_numeric(vendas[column], errors="coerce").fillna(0)
    vendas["_faturamento"] = vendas["faturamento"].where(
        vendas["faturamento"] > 0, vendas["quantidade_vendida"] * vendas["preco_venda"]
    )
    vendas["_custo_vendas"] = vendas["quantidade_vendida"] * vendas["preco_compra"]
    vs = vendas.groupby(["codigo_barras", "_descricao_match"], as_index=False).agg(
        quantidade_vendida=("quantidade_vendida", "sum"),
        _faturamento=("_faturamento", "sum"),
        _custo_vendas=("_custo_vendas", "sum"),
    ).rename(columns={"_descricao_match": "descricao_norm"})
    # Cada preço de venda (coluna F) com a quantidade e o faturamento daquele
    # preço, do maior para o menor, para o card mostrar de onde vem o total.
    priced = vendas[(vendas.quantidade_vendida > 0) & (vendas.preco_venda > 0)].copy()
    priced["preco"] = priced.preco_venda.round(2)
    tiers = priced.groupby(["codigo_barras", "_descricao_match", "preco"], as_index=False).agg(
        quantidade=("quantidade_vendida", "sum"), faturamento=("_faturamento", "sum"),
    ).sort_values("preco", ascending=False, kind="stable")
    price_lists = {
        key: [
            {"preco_venda": float(r.preco), "quantidade": float(r.quantidade), "faturamento": float(r.faturamento)}
            for r in group.itertuples(index=False)
        ]
        for key, group in tiers.groupby(["codigo_barras", "_descricao_match"], sort=False)
    }
    vs["precos_venda"] = [price_lists.get(key, []) for key in zip(vs.codigo_barras, vs.descricao_norm)]

    merged = estoque.merge(vs, on=["codigo_barras", "descricao_norm"], how="left")
    for column in ("quantidade_vendida", "_faturamento", "_custo_vendas"):
        merged[column] = merged[column].fillna(0)
    merged["precos_venda"] = [v if isinstance(v, list) else [] for v in merged["precos_venda"]]
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
    sales_keys = set(zip(vendas.codigo_barras, vendas["_descricao_match"]))
    unmatched_mask = [
        key not in stock_keys
        for key in zip(vendas.codigo_barras, vendas["_descricao_match"])
    ]
    unmatched_sales = vendas.loc[unmatched_mask]
    unmatched_products = unmatched_sales.groupby(
        ["codigo_barras", "descricao_norm"], as_index=False
    ).agg(
        descricao=("descricao", "first"),
        quantidade_vendida=("quantidade_vendida", "sum"),
    )
    unmatched_items = [
        {
            "codigo_barras": str(row.codigo_barras),
            "descricao": str(row.descricao),
            "loja": str(loja),
            "quantidade_vendida": float(row.quantidade_vendida),
        }
        for row in unmatched_products.itertuples(index=False)
    ]

    # Preços e faturamento vêm da planilha de vendas (D compra, F venda,
    # G faturamento). Sem venda no período, o preço de venda é o atual da
    # planilha de estoque (coluna F); 2x o preço de compra só quando ela vier vazia.
    merged["preco_compra_estoque"] = pd.to_numeric(merged["preco_compra"], errors="coerce").fillna(0)
    sold = merged.quantidade_vendida > 0
    sold_qty = merged.quantidade_vendida.where(sold, 1)
    has_sales_cost = sold & (merged._custo_vendas > 0)
    has_sales_revenue = sold & (merged._faturamento > 0)
    merged["preco_compra"] = (merged._custo_vendas / sold_qty).where(
        has_sales_cost, merged.preco_compra_estoque
    )
    stock_price = merged.preco_venda_estoque.where(merged.preco_venda_estoque > 0, merged.preco_compra * 2)
    merged["preco_venda"] = (merged._faturamento / sold_qty).where(has_sales_revenue, stock_price)
    # O valor do estoque continua usando o custo da planilha de estoque.
    merged["valor_estoque"] = merged.quantidade_estoque * merged.preco_compra_estoque
    merged["valor_vendido"] = merged._faturamento.where(
        has_sales_revenue, merged.quantidade_vendida * merged.preco_venda
    )
    # Vendido por 2 ou mais preços: o preço de venda exibido é o atual, da
    # planilha de estoque (coluna F). O preço médio segue em preco_venda.
    many_prices = merged["precos_venda"].map(len) > 1
    merged["preco_venda_atual"] = merged.preco_venda_estoque.where(
        many_prices & (merged.preco_venda_estoque > 0)
    )
    merged.drop(columns=["_faturamento", "_custo_vendas", "preco_venda_estoque"], inplace=True)
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
        if q < 0: return "NEGATIVO"          # venda sem entrada no sistema
        if q == 0: return "SEM ESTOQUE"
        if q <= config.estoque_critico: return "CRÍTICO"
        if q <= config.estoque_baixo: return "BAIXO"
        if v <= 0: return "SEM VENDA"
        if r.cobertura >= config.excesso_cobertura: return "EXCESSO"
        return "NORMAL"
    merged["status_estoque"] = merged.apply(status, axis=1)

    audit = {
        "produtos_estoque": len(estoque), "produtos_vendas": len(vendas),
        "vendas_correspondentes": len(sales_keys & stock_keys), "vendas_sem_correspondencia": len(sales_keys - stock_keys),
        "produtos_ignorados": ig1 + ig2,
        "codigos_invalidos": sum(
            int((frame.codigo_barras.map(normalize_barcode) == "").sum())
            for frame in (df_estoque, df_vendas) if "codigo_barras" in frame
        ),
        "descricoes_divergentes": len(sales_keys - stock_keys),
        "produtos_sem_classificacao": int((merged.grupo == "SEM CLASSIFICAÇÃO").sum()),
        "vendas_sem_correspondencia_itens": unmatched_items,
    }
    return merged, audit

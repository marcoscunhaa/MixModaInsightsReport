import pandas as pd

from core.stores import order_stores, store_sort_key
from utils.normalization import barcode_sort_key

def filter_analysis(df,loja="Todas",grupo="Todos",subclasse="Todas",busca="",status="Todos"):
    out=df
    if loja!="Todas":out=out[out.loja==loja]
    if grupo!="Todos":out=out[out.grupo==grupo]
    if subclasse!="Todas":out=out[out.subclasse==subclasse]
    if status!="Todos":out=out[out.status_estoque==status]
    if busca.strip():
        q=busca.strip().upper()
        m=(out.descricao.str.upper().str.contains(q,na=False,regex=False)|out.codigo_barras.str.contains(q,na=False,regex=False)|out.grupo.str.upper().str.contains(q,na=False,regex=False)|out.subclasse.str.upper().str.contains(q,na=False,regex=False))
        # Leitor de código de barras entrega o EAN com zeros à esquerda; o código
        # da análise é guardado sem eles.
        if q.isdigit() and q.lstrip("0"):
            m=m|out.codigo_barras.str.contains(q.lstrip("0"),na=False,regex=False)
        out=out[m]
    return out

def kpis(df):
    return {"Valor em estoque":df.valor_estoque.sum(),"Unidades em estoque":df.quantidade_estoque.sum(),
    "Unidades vendidas":df.quantidade_vendida.sum(),"Produtos ativos analisados":len(df),
    "Produtos sem vendas":int(df.produto_sem_venda.sum()),"Produtos em ruptura":int(df.ruptura.sum()),
    "Produtos críticos":int((df.status_estoque=="CRÍTICO").sum()),"Giro médio":df.giro.mean() if len(df) else 0,
    "Margem potencial":(df.margem_unitaria*df.quantidade_estoque).sum(),"Faturamento estimado":df.valor_vendido.sum()}

def pivot_by_store(df, value="quantidade_estoque", ascending=False):
    """Uma métrica (`value`) de cada produto por loja, uma coluna por loja.

    O produto é identificado pelo código de barras, porque a descrição pode
    variar entre lojas; o nome exibido é o mais frequente. Loja sem linha do
    produto em `df` fica vazia (NaN), diferente de zero.
    Colunas de loja na ordem oficial (core.stores) e linhas pelo código de
    barras, do menor para o maior: assim a grade de tamanhos fica em sequência
    (P, M, G, GG). `ascending` é mantido só por compatibilidade.
    Retorna (tabela, lojas, totais por loja).
    """
    if df.empty:
        return df.iloc[0:0], [], {}
    stores = order_stores(df.loja.dropna().unique())
    names = (df.groupby("codigo_barras").descricao
             .agg(lambda s: s.value_counts().index[0]).rename("descricao"))
    groups = df.groupby("codigo_barras")[["grupo", "subclasse"]].first()
    pivot = df.pivot_table(index="codigo_barras", columns="loja", values=value,
                           aggfunc="sum").reindex(columns=stores)
    table = pd.concat([names, groups, pivot], axis=1).reset_index()
    table["total"] = table[stores].sum(axis=1, min_count=1).fillna(0)
    table = table.sort_values("codigo_barras", key=lambda col: col.map(barcode_sort_key), kind="stable").reset_index(drop=True)
    totals = {store: float(df.loc[df.loja == store, value].sum()) for store in stores}
    return table, stores, totals


def stock_by_store(df):
    """Unidades em estoque de cada produto por loja."""
    return pivot_by_store(df, "quantidade_estoque")


def single_product_labels(df):
    """Com um único produto na análise, KPIs de contagem viram texto legível.

    Retorna {} quando há mais (ou menos) de um produto: aí os números fazem sentido.
    """
    if len(df) != 1:
        return {}
    row = df.iloc[0]
    stock = float(row.quantidade_estoque)
    return {
        "Produtos ativos": "1 PRODUTO",
        "Sem vendas": "SEM VENDAS" if row.quantidade_vendida <= 0 else "COM VENDAS",
        "Em ruptura": "ESTOQUE NEGATIVO" if stock < 0 else "SEM ESTOQUE" if stock == 0 else "COM ESTOQUE",
        "Críticos": str(row.status_estoque),
    }


def top_sold(df,n=10):
    return df.sort_values(
        ["quantidade_vendida", "valor_vendido"],
        ascending=[False, False],
        kind="stable",
    ).head(n)


def stagnant(df,n=10):
    return (
        df[(df.quantidade_estoque > 0) & (df.quantidade_vendida <= 0)]
        .sort_values(["valor_estoque", "quantidade_estoque"], ascending=[False, False], kind="stable")
        .head(n)
    )


def idle_stock(df,n=20):
    """Estoque parado: sem venda no período, ordenado pela maior quantidade em estoque."""
    return (
        df[(df.quantidade_estoque > 0) & (df.quantidade_vendida <= 0)]
        .sort_values(["quantidade_estoque", "valor_estoque"], ascending=[False, False], kind="stable")
        .head(n)
    )


def rupture(df,n=None):
    """Rank stockout products by observed demand, then estimated sales value."""
    x = df[df.ruptura].sort_values(
        ["quantidade_vendida", "valor_vendido"],
        ascending=[False, False],
        kind="stable",
    )
    return x if n is None else x.head(n)


def critical(df,n=None):
    """Rank replenishment attention by severity, coverage risk, and demand."""
    x = df[df.status_estoque.isin(["NEGATIVO", "SEM ESTOQUE", "CRÍTICO", "BAIXO"])].copy()
    status_priority = {"NEGATIVO": 0, "SEM ESTOQUE": 0, "CRÍTICO": 1, "BAIXO": 2}
    x["_prioridade_status"] = x.status_estoque.map(status_priority)
    x = x.sort_values(
        ["_prioridade_status", "risco_ruptura", "cobertura", "quantidade_vendida", "valor_vendido"],
        ascending=[True, False, True, False, False],
        kind="stable",
    ).drop(columns="_prioridade_status")
    return x if n is None else x.head(n)


def sort_products(df):
    """Linhas de produto pelo código de barras (menor → maior) e, no mesmo código, pela ordem das lojas."""
    if df.empty:
        return df
    keys = df.codigo_barras.map(barcode_sort_key)
    stores = df.loja.map(store_sort_key) if "loja" in df else None
    order = sorted(range(len(df)), key=lambda i: (keys.iloc[i], stores.iloc[i] if stores is not None else 0))
    return df.iloc[order]


def product_options(df):
    """Um item por código de barras (nome mais frequente, grupo e subclasse), do menor código para o maior.

    Usado pela seleção de produtos: marcando os tamanhos de um conjunto, eles
    aparecem em sequência (P → GG) porque os códigos da grade são sequenciais.
    """
    if df.empty:
        return []
    names = df.groupby("codigo_barras").descricao.agg(lambda s: s.value_counts().index[0])
    info = df.groupby("codigo_barras")[["grupo", "subclasse"]].first()
    options = [
        {"codigo_barras": code, "descricao": str(names[code]),
         "grupo": str(info.at[code, "grupo"]), "subclasse": str(info.at[code, "subclasse"])}
        for code in names.index
    ]
    return sorted(options, key=lambda o: barcode_sort_key(o["codigo_barras"]))


def match_options(options, query):
    """Filtra pelo texto digitado: todas as palavras no nome/subclasse, ou parte do código."""
    from utils.normalization import normalize_barcode, normalize_text
    words = normalize_text(query).split()
    digits = normalize_barcode(query) if any(ch.isdigit() for ch in str(query)) else ""
    if not words:
        return list(options)
    found = []
    for option in options:
        text = normalize_text(f"{option['descricao']} {option['subclasse']} {option['grupo']} {option['codigo_barras']}")
        if all(word in text for word in words) or (
            digits not in ("", "0") and digits in normalize_barcode(option["codigo_barras"])
        ):
            found.append(option)
    return found


# ---------- um produto por código (lojas juntas) ----------

# Status mais grave primeiro: entre lojas, vale o pior para o produto.
STATUS_SEVERITY = ["NEGATIVO", "SEM ESTOQUE", "CRÍTICO", "BAIXO", "SEM VENDA", "EXCESSO", "NORMAL"]
_SEVERITY = {status: i for i, status in enumerate(STATUS_SEVERITY)}


def _code_keys(df):
    from utils.normalization import normalize_barcode
    return df.codigo_barras.map(normalize_barcode)


def merge_stores(df):
    """Um registro por código de barras, somando as lojas (vetorizado).

    Produto que está numa loja só fica exatamente como veio. Nos demais,
    quantidades, faturamento e valor em estoque são somados, preços viram médias,
    giro/cobertura/margem são recalculados, o status é o mais grave e `loja`
    lista as lojas na ordem oficial ("Sitio São João, Palmeiras, ...").
    `n_lojas` diz em quantas lojas o produto está.
    """
    if df.empty:
        out = df.copy()
        out["n_lojas"] = pd.Series(dtype=int)
        return out
    work = df.copy()
    work["_key"] = _code_keys(work)
    work["_ordem"] = work.loja.map(store_sort_key)
    work = work.sort_values(["_key", "_ordem"], kind="stable")
    sizes = work.groupby("_key")["_key"].transform("size")
    single = work[sizes == 1].copy()
    single["n_lojas"] = 1
    multi = work[sizes > 1]
    parts = [single]
    if not multi.empty:
        g = multi.groupby("_key", sort=False)
        first = g.first()
        out = first.copy()
        for col in ("quantidade_estoque", "quantidade_vendida", "valor_vendido", "valor_estoque"):
            if col in multi:
                out[col] = g[col].sum()
        out["loja"] = g["loja"].agg(lambda s: ", ".join(dict.fromkeys(s.astype(str))))
        out["n_lojas"] = g["loja"].nunique()
        if "preco_compra" in multi:
            out["preco_compra"] = multi.preco_compra.where(multi.preco_compra > 0).groupby(multi["_key"]).mean().fillna(0)
        if "preco_venda" in multi:
            avg_price = multi.preco_venda.where(multi.preco_venda > 0).groupby(multi["_key"]).mean().fillna(0)
            sold = out.quantidade_vendida > 0
            revenue = out.get("valor_vendido", pd.Series(0, index=out.index))
            out["preco_venda"] = (revenue / out.quantidade_vendida.where(sold, 1)).where(sold & (revenue > 0), avg_price)
        if "preco_compra" in out and "preco_venda" in out:
            out["margem_unitaria"] = out.preco_venda - out.preco_compra
            out["margem_percentual"] = (out.margem_unitaria / out.preco_venda.where(out.preco_venda != 0) * 100).fillna(0)
        total = out.quantidade_vendida + out.quantidade_estoque
        out["giro"] = (out.quantidade_vendida / total.where(total > 0) * 100).fillna(0)
        out["cobertura"] = (out.quantidade_estoque / out.quantidade_vendida.where(out.quantidade_vendida > 0)).fillna(float("inf"))
        out["produto_sem_venda"] = out.quantidade_vendida <= 0
        for col in ("ruptura", "risco_ruptura"):
            if col in multi:
                out[col] = g[col].any()
        if "status_estoque" in multi:
            worst = multi.status_estoque.map(lambda s: _SEVERITY.get(s, 99)).groupby(multi["_key"]).min()
            out["status_estoque"] = worst.map(lambda i: STATUS_SEVERITY[i] if i < len(STATUS_SEVERITY) else "—")
        if "precos_venda" in out:
            out["precos_venda"] = [[] for _ in range(len(out))]  # vários preços por loja não somam
        if "preco_venda_atual" in out:
            out["preco_venda_atual"] = float("nan")
        parts.append(out.reset_index())
    merged = pd.concat(parts, ignore_index=True)
    merged = merged.sort_values("codigo_barras", key=lambda col: col.map(barcode_sort_key), kind="stable")
    return merged.drop(columns=["_key", "_ordem"], errors="ignore").reset_index(drop=True)


def _per_store(rows):
    def num(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return v if v == v else 0.0
    return [
        {
            "loja": str(r.get("loja", "")),
            "descricao": str(r.get("descricao", "")),
            "quantidade_estoque": num(r.get("quantidade_estoque")),
            "quantidade_vendida": num(r.get("quantidade_vendida")),
            "valor_vendido": num(r.get("valor_vendido")),
            "preco_compra": num(r.get("preco_compra")),
            "preco_venda": num(r.get("preco_venda")),
            "status_estoque": str(r.get("status_estoque", "")),
        }
        for r in rows
    ]


def product_detail(df, codigo_barras):
    """Registro do card de um produto: lojas juntas + `por_loja` (ordem oficial das lojas)."""
    from utils.normalization import normalize_barcode
    rows = df[_code_keys(df) == normalize_barcode(codigo_barras)] if not df.empty else df
    if rows.empty:
        return None
    rows = rows.iloc[sorted(range(len(rows)), key=lambda i: store_sort_key(rows.loja.iloc[i]))]
    record = merge_stores(rows).iloc[0].to_dict()
    record["lojas"] = order_stores(dict.fromkeys(rows.loja.astype(str)))
    record["por_loja"] = _per_store(rows.to_dict("records"))
    return record


def merge_by_barcode(df):
    """Lista de registros (um por código), cada um com `lojas` e `por_loja`."""
    if df.empty:
        return []
    keys = _code_keys(df)
    records = []
    for _key, part in df.groupby(keys, sort=False):
        part = part.iloc[sorted(range(len(part)), key=lambda i: store_sort_key(part.loja.iloc[i]))]
        record = merge_stores(part).iloc[0].to_dict()
        record["lojas"] = order_stores(dict.fromkeys(part.loja.astype(str)))
        record["por_loja"] = _per_store(part.to_dict("records"))
        records.append(record)
    return sorted(records, key=lambda r: barcode_sort_key(r["codigo_barras"]))


def product_count(df):
    """Produtos distintos: o mesmo código em várias lojas conta uma vez."""
    return int(_code_keys(df).nunique()) if not df.empty else 0

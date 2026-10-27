from utils.normalization import normalize_barcode, normalize_text

def is_produto_ignorado(descricao, codigo_barras=None):
    s=normalize_text(descricao)
    codigo = normalize_barcode(codigo_barras)
    return (
        s.startswith("CODIGO DESATIVADO")
        or s.startswith("PECA")
        or len(codigo) in (3, 4)
    )

def clean_dataframe(df, description_col="descricao", barcode_col="codigo_barras"):
    if description_col not in df.columns: return df.copy(),0
    if barcode_col in df.columns:
        ignored = df.apply(lambda row: is_produto_ignorado(row[description_col], row[barcode_col]), axis=1)
    else:
        ignored = df[description_col].map(is_produto_ignorado)
    mask=~ignored
    return df.loc[mask].copy().reset_index(drop=True), int((~mask).sum())

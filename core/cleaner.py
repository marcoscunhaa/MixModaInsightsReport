from utils.normalization import normalize_text

def is_produto_ignorado(descricao):
    s=normalize_text(descricao)
    return s.startswith("CODIGO DESATIVADO") or s.startswith("PECA")

def clean_dataframe(df, description_col="descricao"):
    if description_col not in df.columns: return df.copy(),0
    mask=~df[description_col].map(is_produto_ignorado)
    return df.loc[mask].copy().reset_index(drop=True), int((~mask).sum())

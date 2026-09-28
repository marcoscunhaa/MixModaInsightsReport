import re, unicodedata, math

def normalize_text(value):
    if value is None or (isinstance(value, float) and math.isnan(value)): return ""
    s = str(value).strip().upper()
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()

def normalize_barcode(value):
    if value is None or (isinstance(value,float) and math.isnan(value)): return ""
    if isinstance(value,float) and value.is_integer(): s=str(int(value))
    else: s=str(value).strip()
    if "E+" in s.upper():
        try: s=format(float(s),".0f")
        except Exception: pass
    s=re.sub(r"\D","",s)
    return s.lstrip("0") or "0"

def to_number(value, default=0.0):
    if value is None or (isinstance(value,float) and math.isnan(value)): return default
    if isinstance(value,(int,float)): return float(value)
    s=str(value).strip().replace("R$","").replace(" ","")
    if "," in s and "." in s: s=s.replace(".","").replace(",",".")
    elif "," in s: s=s.replace(",",".")
    try: return float(s)
    except Exception: return default

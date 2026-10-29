import re, unicodedata, math
from datetime import date, datetime, time, timedelta

# Excel conta dias a partir de 1899-12-30; antes de 01/03/1900 o leitor usa
# 1899-12-31 por causa do 29/02/1900 inexistente (mesma regra do xlrd/openpyxl).
_EXCEL_EPOCH = datetime(1899, 12, 30)
_EXCEL_EPOCH_BEFORE_MARCH_1900 = datetime(1899, 12, 31)


def excel_serial(value):
    """Desfaz a conversão de um número que a planilha formatou como data/hora.

    As extrações da Mix Moda trazem quantidades e preços com formato de hora
    (`h:mm AM/PM`), e o leitor de Excel entrega datetime/time no lugar do número.
    """
    if isinstance(value, timedelta):
        return value.total_seconds() / 86400
    if isinstance(value, time):
        return (value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6) / 86400
    if isinstance(value, datetime):
        epoch = _EXCEL_EPOCH_BEFORE_MARCH_1900 if value < datetime(1900, 3, 1) else _EXCEL_EPOCH
        return round((value - epoch).total_seconds() / 86400, 6)
    if isinstance(value, date):
        return excel_serial(datetime(value.year, value.month, value.day))
    return None

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
    serial = excel_serial(value)
    if serial is not None: return serial
    s=str(value).strip().replace("R$","").replace(" ","")
    if "," in s and "." in s: s=s.replace(".","").replace(",",".")
    elif "," in s: s=s.replace(",",".")
    try: return float(s)
    except Exception: return default

def br_number(value, decimals=0):
    try:
        s=f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')

def brl(value, decimals=2):
    return f"R$ {br_number(value, decimals)}"

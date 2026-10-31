# Amounts come from Brazilian spreadsheets, so they are in Brazilian reais (BRL).
# Change CURRENCY_SYMBOL if the source data uses another currency.
CURRENCY_SYMBOL = "R$"


def fmt_number(value, decimals=0):
    """Format a number with US-style separators: 12,345.67."""
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_money(value, decimals=2):
    return f"{CURRENCY_SYMBOL} {fmt_number(value, decimals)}"

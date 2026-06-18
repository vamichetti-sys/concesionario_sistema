from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name="miles")
def miles(value):
    """Formatea un número con separador de miles "." (formato argentino).

    Solo parte entera (sin decimales): 7211600 -> "7.211.600".
    Si no es numérico, devuelve el valor tal cual.
    """
    if value is None or value == "":
        return value
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    negativo = d < 0
    entero = int(abs(d))
    s = f"{entero:,}".replace(",", ".")
    return f"-{s}" if negativo else s

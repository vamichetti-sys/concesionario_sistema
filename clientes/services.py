from datetime import date
from cuentas.models import CuotaPlan
from .models import ReglaComercial


# ==========================================================
# RECÁLCULO DE CUMPLIMIENTO DE PAGO DEL CLIENTE
# ==========================================================
def recalcular_cumplimiento_cliente(cliente):
    """
    Reglas:
    - Verde: hasta 10 días de atraso
    - Amarillo: entre 30 y 50 días de atraso
    - Rojo: más de 50 días de atraso o cuotas impagas graves
    """

    hoy = date.today()

    cuotas = CuotaPlan.objects.filter(
        plan__cuenta_corriente__cliente=cliente
    )

    # Si nunca tuvo cuotas → cliente confiable
    if not cuotas.exists():
        cliente.cumplimiento_pago = 'verde'
        cliente.save()
        return

    max_atraso = 0

    for cuota in cuotas:
        if cuota.estado == 'pagada':
            atraso = (
                (cuota.fecha_pago - cuota.fecha_vencimiento).days
                if hasattr(cuota, 'fecha_pago')
                else 0
            )
        else:
            atraso = (hoy - cuota.fecha_vencimiento).days

        if atraso > max_atraso:
            max_atraso = atraso

    if max_atraso <= 10:
        cliente.cumplimiento_pago = 'verde'
    elif 30 <= max_atraso <= 50:
        cliente.cumplimiento_pago = 'amarillo'
    else:
        cliente.cumplimiento_pago = 'rojo'

    cliente.save()


# ==========================================================
# OBTENER REGLA COMERCIAL SEGÚN CUMPLIMIENTO DEL CLIENTE
# ==========================================================
def obtener_regla_comercial(cliente):
    """
    Devuelve la regla comercial asociada al color de cumplimiento
    del cliente (verde / amarillo / rojo).

    No calcula nada, solo consulta configuración.
    """
    try:
        return ReglaComercial.objects.get(
            color_cliente=cliente.cumplimiento_pago
        )
    except ReglaComercial.DoesNotExist:
        return None

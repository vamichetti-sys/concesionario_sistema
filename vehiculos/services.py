from datetime import date
from decimal import Decimal

from vehiculos.models import FichaVehicular


def recalcular_cuentas_vinculadas(vehiculo):
    """
    Recalcula el saldo/estado de las cuentas corrientes vinculadas a un
    vehículo. Se llama cuando se actualiza la ficha (gastos de ingreso,
    datos, etc.) para que las cuentas del cliente queden sincronizadas.

    Un vehículo puede estar vinculado a una cuenta:
      - como unidad vendida (vehiculo.venta.cuenta_corriente), o
      - como permuta (movimientos origen="permuta" en la cuenta).

    Nunca interrumpe el flujo: si algo falla, se ignora.
    """
    from cuentas.models import CuentaCorriente

    cuentas = {}

    # Cuenta del comprador (vía venta)
    try:
        venta = getattr(vehiculo, "venta", None)
        if venta is not None:
            cc = getattr(venta, "cuenta_corriente", None)
            if cc is not None:
                cuentas[cc.pk] = cc
    except Exception:
        pass

    # Cuentas donde el vehículo figura como permuta
    try:
        for cc in CuentaCorriente.objects.filter(
            movimientos__vehiculo=vehiculo,
            movimientos__origen="permuta",
        ).distinct():
            cuentas[cc.pk] = cc
    except Exception:
        pass

    for cc in cuentas.values():
        try:
            cc.recalcular_saldo()
        except Exception:
            pass


def actualizar_gastos_por_vencimientos():
    """
    Revisa todos los vehiculos en stock y auto-acumula SOLO las patentes
    mensuales en gastos de concesionario (cada vencimiento posterior a la
    fecha de ingreso suma una patente mensual).

    NOTA: VTV, verificación y grabado de autopartes ya NO se copian
    automáticamente. El gasto de INGRESO de esos trámites es deuda del
    vehículo (lo paga el cliente/proveedor), no un costo de la concesionaria:
    si la concesionaria efectivamente lo paga, se carga A MANO en
    "Gastos concesionario".
    """
    fichas = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
    ).select_related("vehiculo")

    actualizados = 0

    for ficha in fichas:
        if acumular_patentes_mensuales(ficha):
            ficha.save(update_fields=["gc_patentes"])
            actualizados += 1

    return actualizados


def acumular_patentes_mensuales(ficha, hoy=None):
    """Para UNA ficha: acumula en gc_patentes una "patente mensual" por cada
    vencimiento que YA pasó y es POSTERIOR (o igual) a la fecha de ingreso.

    Devuelve True si modificó ficha.gc_patentes (NO guarda; eso lo hace quien
    llama). Solo aumenta gc_patentes, nunca lo baja, para no pisar cargas
    manuales.

    (La deuda de patentes AL ingreso —patentes_monto— es otra cosa: es un gasto
     de INGRESO, no de concesionario.)
    """
    hoy = hoy or date.today()

    mensual = ficha.patente_mensual or Decimal("0")
    if mensual <= 0:
        return False

    f_ing = getattr(ficha.vehiculo, "fecha_ingreso", None)
    vencimientos_patentes = [
        ficha.patentes_vto1,
        ficha.patentes_vto2,
        ficha.patentes_vto3,
        ficha.patentes_vto4,
        ficha.patentes_vto5,
    ]
    cuotas_vencidas = sum(
        1 for vto in vencimientos_patentes
        if vto and vto < hoy and (f_ing is None or vto >= f_ing)
    )

    total_patentes_esperado = mensual * cuotas_vencidas
    actual = ficha.gc_patentes or Decimal("0")

    if total_patentes_esperado > actual:
        ficha.gc_patentes = total_patentes_esperado
        return True
    return False

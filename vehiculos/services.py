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
    hoy = date.today()

    fichas = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
    ).select_related("vehiculo")

    actualizados = 0

    for ficha in fichas:
        cambios = []

        # Patentes mensuales: cada vencimiento que cae DESPUÉS de la fecha de
        # ingreso y que ya pasó suma una "patente mensual" a gastos de
        # concesionario, acumulando hasta que el vehículo se vende.
        # (La deuda de patentes AL ingreso —patentes_monto— es otra cosa: es un
        #  gasto de INGRESO, no de concesionario.)
        mensual = ficha.patente_mensual or Decimal("0")
        if mensual > 0:
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

            if total_patentes_esperado > ficha.gc_patentes:
                ficha.gc_patentes = total_patentes_esperado
                cambios.append("gc_patentes")

        if cambios:
            ficha.save(update_fields=cambios)
            actualizados += 1

    return actualizados

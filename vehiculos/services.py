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
    Revisa todos los vehiculos en stock y auto-llena gastos de concesionario
    cuando un vencimiento ya paso:
    - VTV vencida → gc_vtv se llena con gasto_vtv
    - Verificacion vencida → gc_verificacion se llena con gasto_verificacion
    - Patentes vencidas → gc_patentes se acumula con patentes_monto por cada cuota vencida
    """
    hoy = date.today()

    fichas = FichaVehicular.objects.filter(
        vehiculo__estado="stock",
    ).select_related("vehiculo")

    actualizados = 0

    for ficha in fichas:
        cambios = []

        # VTV vencida
        if (
            ficha.vtv_vencimiento
            and ficha.vtv_vencimiento < hoy
            and ficha.gc_vtv == 0
            and ficha.gasto_vtv
            and ficha.gasto_vtv > 0
        ):
            ficha.gc_vtv = ficha.gasto_vtv
            cambios.append("gc_vtv")

        # Verificacion policial vencida
        if (
            ficha.verificacion_vencimiento
            and ficha.verificacion_vencimiento < hoy
            and ficha.gc_verificacion == 0
            and ficha.gasto_verificacion
            and ficha.gasto_verificacion > 0
        ):
            ficha.gc_verificacion = ficha.gasto_verificacion
            cambios.append("gc_verificacion")

        # Grabado autopartes (si el turno paso y no tiene gasto)
        if (
            ficha.autopartes_turno
            and ficha.autopartes_turno < hoy
            and ficha.gc_grabado_autopartes == 0
            and ficha.gasto_autopartes
            and ficha.gasto_autopartes > 0
        ):
            ficha.gc_grabado_autopartes = ficha.gasto_autopartes
            cambios.append("gc_grabado_autopartes")

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

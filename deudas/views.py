from django.shortcuts import render
from django.db.models import Q

from cuentas.models import CuentaCorriente
from vehiculos.models import Vehiculo


def listado_deudas(request):
    """
    Lista deudas pendientes:
    - Deudas de clientes (CuentaCorriente con saldo > 0)
    - Deudas por gastos de ingreso impagos (Vehículo)
    """

    q = request.GET.get("q", "").strip()

    deudas = []

    # ======================================================
    # 1️⃣ DEUDAS DE CUENTAS CORRIENTES (CLIENTES)
    # ======================================================
    cuentas = (
        CuentaCorriente.objects
        .select_related(
            "cliente",
            "venta",
            "venta__vehiculo"
        )
        .filter(saldo__gt=0)
    )

    if q:
        cuentas = cuentas.filter(
            Q(venta__vehiculo__dominio__icontains=q) |
            Q(venta__vehiculo__marca__icontains=q) |
            Q(venta__vehiculo__modelo__icontains=q)
        )

    for cuenta in cuentas:
        vehiculo = cuenta.venta.vehiculo if cuenta.venta else None

        deudas.append({
            "tipo": "cuenta",
            "vehiculo": vehiculo,
            "cliente": cuenta.cliente,
            "estado": cuenta.get_estado_display(),
            "total_deuda": cuenta.saldo,
            "cuenta": cuenta,
        })

    # ======================================================
    # 2️⃣ DEUDAS POR GASTOS DE INGRESO (VEHÍCULOS)
    # ======================================================
    vehiculos = Vehiculo.objects.prefetch_related("pagos_gastos_ingreso")

    if q:
        vehiculos = vehiculos.filter(
            Q(dominio__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo__icontains=q)
        )

    for vehiculo in vehiculos:

        gastos = list(vehiculo.pagos_gastos_ingreso.all())

        if not gastos:
            continue

        deuda_gastos = 0

        for gasto in gastos:
            # 🔒 criterio seguro:
            # si el gasto tiene campo 'estado' y NO está cerrado → deuda
            if hasattr(gasto, "estado"):
                if gasto.estado != "pagado":
                    deuda_gastos += getattr(gasto, "monto", 0)
            else:
                # fallback: si no hay estado, se considera deuda
                deuda_gastos += getattr(gasto, "monto", 0)

        if deuda_gastos <= 0:
            continue

        # Evitar duplicar si ya figura por cuenta corriente
        ya_listado = any(
            d["vehiculo"] and d["vehiculo"].id == vehiculo.id
            for d in deudas
        )
        if ya_listado:
            continue

        deudas.append({
            "tipo": "gasto",
            "vehiculo": vehiculo,
            "cliente": None,
            "estado": "Gastos de ingreso",
            "total_deuda": deuda_gastos,
            "cuenta": None,
        })

    return render(
        request,
        "deudas/listado.html",
        {
            "deudas": deudas,
            "query": q,
        }
    )

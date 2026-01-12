from django.shortcuts import render
from django.db.models import Q, Sum

from cuentas.models import CuentaCorriente
from vehiculos.models import Vehiculo, FichaVehicular, PagoGastoIngreso


def listado_deudas(request):
    """
    Vehículos con deuda (GASTOS).
    La lógica de cuentas corrientes se conserva,
    pero NO se ejecuta en esta pantalla.
    """

    q = request.GET.get("q", "").strip()
    deudas = []

    # ======================================================
    # ⚠️ BLOQUE DE CUENTAS CORRIENTES (CONSERVADO)
    # 👉 NO SE EJECUTA EN ESTA VISTA
    # ======================================================
    MOSTRAR_CUENTAS_CORRIENTES = False

    if MOSTRAR_CUENTAS_CORRIENTES:
        cuentas = (
            CuentaCorriente.objects
            .select_related("cliente")
            .filter(saldo__gt=0)
        )

        if q:
            cuentas = cuentas.filter(
                Q(cliente__nombre_completo__icontains=q)
            )

        for cuenta in cuentas:
            deudas.append({
                "tipo": "cuenta",
                "vehiculo": None,
                "cliente": cuenta.cliente,
                "estado": cuenta.get_estado_display(),
                "total_deuda": cuenta.saldo,
                "cuenta": cuenta,
            })

    # ======================================================
    # 2️⃣ DEUDAS OPERATIVAS DE VEHÍCULOS (DESDE FICHA)
    # ======================================================
    fichas = FichaVehicular.objects.select_related("vehiculo")

    if q:
        fichas = fichas.filter(
            Q(vehiculo__dominio__icontains=q) |
            Q(vehiculo__marca__icontains=q) |
            Q(vehiculo__modelo__icontains=q)
        )

    for ficha in fichas:
        total_gastos = ficha.total_gastos or 0

        if total_gastos <= 0:
            continue

        total_pagado = (
            PagoGastoIngreso.objects
            .filter(vehiculo=ficha.vehiculo)
            .aggregate(total=Sum("monto"))["total"]
            or 0
        )

        saldo = total_gastos - total_pagado

        if saldo <= 0:
            continue

        deudas.append({
            "tipo": "gasto",
            "vehiculo": ficha.vehiculo,
            "cliente": None,
            "estado": "Gastos de ingreso",
            "total_deuda": saldo,
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

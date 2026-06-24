from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from cuentas.models import CuentaCorriente
from vehiculos.models import Vehiculo, FichaVehicular, PagoGastoIngreso


@login_required
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

        # La deuda de gastos de ingreso es CON EL ENTE. Solo la reducen los
        # pagos que efectivamente saldaron con el organismo. Un "cli_concesion"
        # (el cliente me pagó pero no le pagué al ente) o "pendiente" NO bajan
        # esta deuda. Sin el filtro, la pantalla subdeclaraba la deuda real.
        total_pagado = (
            PagoGastoIngreso.objects
            .filter(
                vehiculo=ficha.vehiculo,
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            )
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
            "vendido": ficha.vehiculo.estado == "vendido",
        })

    # Dividir: vehículos vendidos vs en stock (todo lo que no está vendido)
    deudas_vendidos = [d for d in deudas if d.get("vendido")]
    deudas_stock = [d for d in deudas if not d.get("vendido")]

    # ======================================================
    # 3️⃣ VENDIDOS QUE QUEDARON ADEUDANDO PATENTES O INFRACCIONES
    # ======================================================
    from decimal import Decimal as _D
    vendidos_pat_inf = []
    for ficha in fichas:
        veh = ficha.vehiculo
        if veh.estado != "vendido":
            continue
        saldo_pat = ficha.saldo_por_concepto("Patentes") or _D("0")
        saldo_inf = ficha.saldo_por_concepto("Infracciones") or _D("0")
        saldo_pat = saldo_pat if saldo_pat > 0 else _D("0")
        saldo_inf = saldo_inf if saldo_inf > 0 else _D("0")
        if saldo_pat <= 0 and saldo_inf <= 0:
            continue
        vendidos_pat_inf.append({
            "vehiculo": veh,
            "saldo_patentes": saldo_pat,
            "saldo_infracciones": saldo_inf,
            "total": saldo_pat + saldo_inf,
        })
    vendidos_pat_inf.sort(key=lambda x: x["total"], reverse=True)
    total_vendidos_pat_inf = sum((d["total"] for d in vendidos_pat_inf), _D("0"))

    grupos = [
        {
            "titulo": "En stock",
            "subtitulo": "Vehículos que tenemos y todavía adeudan gastos",
            "icono": "package",
            "color": "#3b82f6",
            "items": deudas_stock,
            "total": sum((d["total_deuda"] for d in deudas_stock), 0),
        },
        {
            "titulo": "Vendidos",
            "subtitulo": "Vehículos ya vendidos que siguen con deuda de gastos",
            "icono": "check-circle",
            "color": "#10b981",
            "items": deudas_vendidos,
            "total": sum((d["total_deuda"] for d in deudas_vendidos), 0),
        },
    ]

    return render(
        request,
        "deudas/listado.html",
        {
            "deudas": deudas,
            "grupos": grupos,
            "vendidos_pat_inf": vendidos_pat_inf,
            "total_vendidos_pat_inf": total_vendidos_pat_inf,
            "query": q,
        }
    )


@login_required
def pdf_listado_deudas(request):
    from datetime import date
    from decimal import Decimal
    from reportes.pdf_utils import render_pdf_listado

    q = request.GET.get("q", "").strip()
    fichas = FichaVehicular.objects.select_related("vehiculo")
    if q:
        fichas = fichas.filter(
            Q(vehiculo__dominio__icontains=q) |
            Q(vehiculo__marca__icontains=q) |
            Q(vehiculo__modelo__icontains=q)
        )

    total = Decimal("0")
    filas = []
    for ficha in fichas:
        total_gastos = ficha.total_gastos or 0
        if total_gastos <= 0:
            continue
        total_pagado = (
            PagoGastoIngreso.objects.filter(
                vehiculo=ficha.vehiculo,
                situacion__in=["prov_directo", "cli_directo", "cli_adelanto", "prov_reintegro"],
            )
            .aggregate(total=Sum("monto"))["total"] or 0
        )
        saldo = total_gastos - total_pagado
        if saldo <= 0:
            continue
        total += Decimal(str(saldo))
        filas.append([
            f"{ficha.vehiculo.marca} {ficha.vehiculo.modelo}",
            ficha.vehiculo.dominio or "—",
            "Gastos de ingreso",
            f"$ {saldo:,.0f}".replace(",", "."),
        ])

    totales = ["", "", "TOTAL", f"$ {total:,.0f}".replace(",", ".")]

    return render_pdf_listado(
        filename="deudas_vehiculos.pdf",
        titulo="Deudas de Vehículos",
        subtitulo=(f"Búsqueda: «{q}» – " if q else "") + f"{len(filas)} unidad(es) con deuda",
        columnas=["Vehículo", "Dominio", "Concepto", "Saldo"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {date.today().strftime('%d/%m/%Y')}",
    )

# ==========================================================
# DEUDAS POR SITUACIÓN DE GASTOS DE INGRESO (solo lectura)
# Solapas: impagas por concesionario / clientes me deben /
#          proveedores me deben / saldadas.
# La gestión del pago se hace SOLO en la ficha del vehículo.
# ==========================================================
@login_required
def deudas_situacion(request):
    from decimal import Decimal
    from compraventa.models import ReintegroProveedor

    CONCEPTOS = {
        "f08": "Formulario 08", "informes": "Informes", "patentes": "Patentes",
        "infracciones": "Infracciones", "verificacion": "Verificación",
        "autopartes": "Autopartes", "vtv": "VTV", "r541": "R541", "firmas": "Firmas",
    }

    tab = request.GET.get("tab", "impagas")
    if tab not in ("impagas", "clientes", "proveedores", "saldadas", "vendidos"):
        tab = "impagas"

    filas = []
    total = Decimal("0")

    if tab == "vendidos":
        # Vehículos ya VENDIDOS (salieron de stock) que todavía tienen saldo de
        # gastos de ingreso pendiente.
        from vehiculos.models import FichaVehicular
        fichas = (
            FichaVehicular.objects
            .filter(vehiculo__estado="vendido")
            .select_related("vehiculo")
        )
        for ficha in fichas:
            try:
                mapa = ficha.mapa_gastos_ingreso()
            except Exception:
                continue
            for concepto_label, monto in mapa.items():
                if not monto or Decimal(monto) <= 0:
                    continue
                saldo = ficha.saldo_por_concepto(concepto_label) or Decimal("0")
                if saldo > 0:
                    filas.append({
                        "vehiculo": ficha.vehiculo,
                        "estado_vehiculo": ficha.vehiculo.get_estado_display(),
                        "concepto": concepto_label,
                        "ente": "—",
                        "monto": saldo,
                        "estado": "Vendido — adeuda gastos",
                    })
                    total += saldo
        filas.sort(key=lambda f: f["monto"], reverse=True)
    elif tab == "proveedores":
        qs = (
            ReintegroProveedor.objects
            .filter(estado="pendiente")
            .select_related("proveedor", "vehiculo")
            .order_by("-creado")
        )
        for r in qs:
            filas.append({
                "vehiculo": r.vehiculo,
                "estado_vehiculo": r.vehiculo.get_estado_display() if r.vehiculo_id else "—",
                "proveedor": r.proveedor.nombre_empresa if r.proveedor_id else "—",
                "concepto": CONCEPTOS.get(r.concepto, r.concepto),
                "ente": r.ente or "—",
                "monto": r.monto,
                "estado": "Pendiente de reintegro",
            })
            total += r.monto or Decimal("0")
    else:
        if tab == "impagas":
            situaciones = ["cli_concesion"]
            filtro = {"saldado": False}
        elif tab == "clientes":
            situaciones = ["cli_adelanto"]
            filtro = {"saldado": False}
        else:  # saldadas
            situaciones = ["prov_directo", "cli_directo", "prov_reintegro", "cli_adelanto", "cli_concesion"]
            filtro = {"saldado": True}

        qs = (
            PagoGastoIngreso.objects
            .filter(situacion__in=situaciones, **filtro)
            .select_related("vehiculo")
            .order_by("-fecha_pago")
        )
        for p in qs:
            filas.append({
                "pago": p,
                "vehiculo": p.vehiculo,
                "estado_vehiculo": p.vehiculo.get_estado_display() if p.vehiculo_id else "—",
                "concepto": CONCEPTOS.get(p.concepto, p.concepto),
                "ente": p.ente or "—",
                "monto": p.monto,
                "estado": p.get_situacion_display(),
                "en_agenda": bool(p.pago_futuro_id),
            })
            if tab != "saldadas":
                total += p.monto or Decimal("0")

    # Contadores para los badges de las solapas
    base = PagoGastoIngreso.objects
    from vehiculos.models import FichaVehicular
    vendidos_con_deuda = 0
    for f in FichaVehicular.objects.filter(vehiculo__estado="vendido").select_related("vehiculo"):
        try:
            if f.tiene_saldo_pendiente():
                vendidos_con_deuda += 1
        except Exception:
            pass
    counts = {
        "impagas": base.filter(situacion="cli_concesion", saldado=False).count(),
        "clientes": base.filter(situacion="cli_adelanto", saldado=False).count(),
        "proveedores": ReintegroProveedor.objects.filter(estado="pendiente").count(),
        "saldadas": base.filter(saldado=True).count(),
        "vendidos": vendidos_con_deuda,
    }

    return render(request, "deudas/situacion.html", {
        "tab": tab,
        "filas": filas,
        "total": total,
        "counts": counts,
        "page_title": "Deudas",
    })

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from datetime import date
from decimal import Decimal

from ventas.models import Venta
from vehiculos.models import Vehiculo
from gestoria.models import Gestoria
from asistencia.models import AsistenciaDiaria
from cuentas.models import CuentaCorriente

from .models import (
    ReporteMensual,
    ReporteAnual,
    FichaReporteInterno,
    GastoReporteInterno,
)
from .forms import (
    FichaReporteInternoForm,
    GastoReporteInternoForm,
)


# ==========================================================
# HELPERS
# ==========================================================
def es_staff(user):
    return user.is_staff


# ==========================================================
# PANTALLA PRINCIPAL DE REPORTES
# ==========================================================
@login_required
def lista_reportes_pdf(request):
    """
    PDF mensual del home de Reportes: resumen del mes seleccionado con
    ventas confirmadas + ganancia + top deudas/cobros.
    """
    from datetime import date as _date
    from decimal import Decimal as _Dec
    from compraventa.models import CompraVentaOperacion, DeudaProveedor
    from cuentas.models import CuentaCorriente
    from vehiculos.models import FichaVehicular, GastoConcesionario
    from reportes.pdf_utils import render_pdf_listado, MESES_ES

    hoy = _date.today()
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    GC_FIELDS = [
        "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
        "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
        "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion",
        "gc_patentes", "gc_otros",
    ]

    def _ganancia(v):
        op = CompraVentaOperacion.objects.filter(vehiculo_id=v.vehiculo_id).first()
        precio_compra = (op.precio_compra if op and op.precio_compra else _Dec("0"))
        ficha = FichaVehicular.objects.filter(vehiculo_id=v.vehiculo_id).first()
        gastos = _Dec("0")
        if ficha:
            for f in GC_FIELDS:
                gastos += getattr(ficha, f, None) or _Dec("0")
        gastos += GastoConcesionario.objects.filter(
            vehiculo_id=v.vehiculo_id
        ).aggregate(t=Sum("monto"))["t"] or _Dec("0")
        precio_venta = v.precio_venta or _Dec("0")
        return precio_venta, precio_compra + gastos, precio_venta - precio_compra - gastos

    ventas = Venta.objects.filter(
        estado="confirmada", fecha_venta__year=anio, fecha_venta__month=mes,
    ).select_related("vehiculo", "cliente").order_by("-fecha_venta")

    filas = []
    t_vta = _Dec("0"); t_cos = _Dec("0"); t_gan = _Dec("0")
    for v in ventas:
        pv, ct, gn = _ganancia(v)
        t_vta += pv; t_cos += ct; t_gan += gn
        filas.append([
            v.fecha_venta.strftime("%d/%m/%Y") if v.fecha_venta else "—",
            f"{v.vehiculo.marca} {v.vehiculo.modelo}" if v.vehiculo_id else "—",
            (v.cliente.nombre_completo if v.cliente_id else "—") or "—",
            f"$ {pv:,.0f}".replace(",", "."),
            f"$ {ct:,.0f}".replace(",", "."),
            f"$ {gn:,.0f}".replace(",", "."),
        ])

    totales = ["", "", "TOTALES",
        f"$ {t_vta:,.0f}".replace(",", "."),
        f"$ {t_cos:,.0f}".replace(",", "."),
        f"$ {t_gan:,.0f}".replace(",", "."),
    ]

    return render_pdf_listado(
        filename=f"reportes_{mes:02d}_{anio}.pdf",
        titulo="Reporte mensual",
        subtitulo=f"{MESES_ES[mes]} {anio} – {len(filas)} venta(s) confirmadas",
        columnas=["Fecha", "Vehículo", "Cliente", "Venta", "Costo+Gastos", "Ganancia"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )


def lista_reportes(request):
    """
    Home del módulo Reportes — 3 paneles:
      1. Ganancias del mes y del año (venta − compra − gastos del vehículo)
      2. Cumplimiento de pagos de clientes (cuotas pagadas vs totales)
      3. Deuda en concesionario (a proveedores + saldo a cobrar a clientes)
    """
    from compraventa.models import CompraVentaOperacion, DeudaProveedor
    from cuentas.models import CuotaPlan, CuentaCorriente, PlanPago
    from vehiculos.models import FichaVehicular, GastoConcesionario

    hoy = date.today()

    # Parametros de período (mes / año seleccionado vía querystring)
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    # ==========================================================
    # 1) GANANCIAS — calculadas a partir de ventas confirmadas
    # ==========================================================
    GC_FIELDS = [
        "gc_service", "gc_mecanica", "gc_chapa_pintura", "gc_tapizado",
        "gc_neumaticos", "gc_vidrios", "gc_cerrajeria", "gc_lavado",
        "gc_gnc", "gc_grabado_autopartes", "gc_vtv", "gc_verificacion",
        "gc_patentes", "gc_otros",
    ]

    def _ganancia_venta(v):
        if not v.vehiculo_id:
            return Decimal("0"), Decimal("0"), Decimal("0")
        # Precio compra (CompraVentaOperacion)
        op = CompraVentaOperacion.objects.filter(vehiculo_id=v.vehiculo_id).first()
        precio_compra = (op.precio_compra if op and op.precio_compra else Decimal("0"))
        # Gastos del vehículo: gc_* en la ficha + GastoConcesionario sueltos
        ficha = FichaVehicular.objects.filter(vehiculo_id=v.vehiculo_id).first()
        gastos = Decimal("0")
        if ficha:
            for f in GC_FIELDS:
                gastos += getattr(ficha, f, None) or Decimal("0")
        gastos += GastoConcesionario.objects.filter(
            vehiculo_id=v.vehiculo_id
        ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

        precio_venta = v.precio_venta or Decimal("0")
        ganancia = precio_venta - precio_compra - gastos
        return precio_venta, precio_compra + gastos, ganancia

    def _resumen_ventas(qs):
        total_ventas  = Decimal("0")
        total_costos  = Decimal("0")
        total_ganan   = Decimal("0")
        detalles = []
        for v in qs.select_related("vehiculo", "cliente").order_by("-fecha_venta"):
            pv, costo, gan = _ganancia_venta(v)
            total_ventas += pv
            total_costos += costo
            total_ganan  += gan
            detalles.append({
                "venta": v,
                "precio_venta": pv,
                "costo_total": costo,
                "ganancia": gan,
            })
        return total_ventas, total_costos, total_ganan, detalles

    ventas_mes_qs = Venta.objects.filter(
        estado="confirmada",
        fecha_venta__year=anio,
        fecha_venta__month=mes,
    )
    tot_v_mes, tot_c_mes, tot_g_mes, detalle_mes = _resumen_ventas(ventas_mes_qs)

    ventas_anio_qs = Venta.objects.filter(
        estado="confirmada",
        fecha_venta__year=anio,
    )
    tot_v_anio, tot_c_anio, tot_g_anio, _ = _resumen_ventas(ventas_anio_qs)

    # Ganancia por mes (gráfico/listado del año seleccionado)
    ganancias_por_mes = []
    for m in range(1, 13):
        qs_m = Venta.objects.filter(
            estado="confirmada",
            fecha_venta__year=anio,
            fecha_venta__month=m,
        )
        _, _, g, _ = _resumen_ventas(qs_m)
        ganancias_por_mes.append({"mes": m, "ganancia": g})

    # ==========================================================
    # 2) CUMPLIMIENTO DE PAGOS DE CLIENTES
    # ==========================================================
    planes_activos = PlanPago.objects.filter(estado="activo").select_related("cuenta", "cuenta__cliente")
    cumplimiento_clientes = []
    cuotas_totales_global  = 0
    cuotas_pagadas_global  = 0
    cuotas_vencidas_global = 0
    for plan in planes_activos:
        cuotas = plan.cuotas.all()
        c_total    = cuotas.count()
        c_pagadas  = cuotas.filter(estado="pagada").count()
        c_vencidas = cuotas.filter(estado="pendiente", vencimiento__lt=hoy).count()
        if c_total == 0:
            continue
        cuotas_totales_global  += c_total
        cuotas_pagadas_global  += c_pagadas
        cuotas_vencidas_global += c_vencidas
        pct = round((c_pagadas / c_total) * 100, 1) if c_total else 0
        cumplimiento_clientes.append({
            "plan": plan,
            "cliente": plan.cuenta.cliente if plan.cuenta_id else None,
            "total": c_total,
            "pagadas": c_pagadas,
            "vencidas": c_vencidas,
            "pct": pct,
        })
    cumplimiento_clientes.sort(key=lambda x: (x["vencidas"], -x["pct"]), reverse=True)

    pct_global = (
        round((cuotas_pagadas_global / cuotas_totales_global) * 100, 1)
        if cuotas_totales_global else 0
    )

    # ==========================================================
    # 3) DEUDA EN CONCESIONARIO
    # ==========================================================
    # 3a) Deuda a proveedores (lo que nosotros debemos)
    deudas_prov = DeudaProveedor.objects.annotate(
        total_pagado=Sum("pagos__monto"),
    )
    deuda_proveedores = Decimal("0")
    detalle_proveedores = []
    for d in deudas_prov.select_related("proveedor", "vehiculo"):
        pagado = d.total_pagado or Decimal("0")
        saldo = (d.monto_total or Decimal("0")) - pagado
        if saldo > 0:
            deuda_proveedores += saldo
            detalle_proveedores.append({
                "proveedor": d.proveedor,
                "vehiculo": d.vehiculo,
                "monto_total": d.monto_total or Decimal("0"),
                "pagado": pagado,
                "saldo": saldo,
            })
    detalle_proveedores.sort(key=lambda x: x["saldo"], reverse=True)

    # 3b) Saldo a cobrar a clientes (lo que nos deben)
    cuentas_a_cobrar = CuentaCorriente.objects.filter(saldo__gt=0).select_related("cliente")
    total_a_cobrar = cuentas_a_cobrar.aggregate(t=Sum("saldo"))["t"] or Decimal("0")
    top_clientes_deudores = cuentas_a_cobrar.order_by("-saldo")[:10]

    context = {
        "page_title": "Reportes",
        "hoy": hoy,
        "mes": mes,
        "anio": anio,
        "anios_disponibles": list(range(hoy.year - 4, hoy.year + 1))[::-1],
        # Ganancias
        "ganan_mes": {
            "total_ventas":  tot_v_mes,
            "total_costos":  tot_c_mes,
            "total_ganan":   tot_g_mes,
            "cantidad":      len(detalle_mes),
        },
        "ganan_anio": {
            "total_ventas": tot_v_anio,
            "total_costos": tot_c_anio,
            "total_ganan":  tot_g_anio,
        },
        "detalle_mes": detalle_mes,
        "ganancias_por_mes": ganancias_por_mes,
        # Cumplimiento
        "cumplimiento_clientes": cumplimiento_clientes,
        "cuotas_totales_global": cuotas_totales_global,
        "cuotas_pagadas_global": cuotas_pagadas_global,
        "cuotas_vencidas_global": cuotas_vencidas_global,
        "pct_global": pct_global,
        # Deuda
        "deuda_proveedores": deuda_proveedores,
        "detalle_proveedores": detalle_proveedores[:15],
        "total_a_cobrar": total_a_cobrar,
        "top_clientes_deudores": top_clientes_deudores,
    }
    return render(request, "reportes/lista.html", context)


# ==========================================================
# REPORTE WEB (OPERATIVO – MENSUAL)
# ==========================================================
@login_required
def reporte_web(request):
    hoy = date.today()

    # ----------------------
    # VENTAS (MES ACTUAL)
    # ----------------------
    total_ventas = Venta.objects.filter(
        fecha_venta__year=hoy.year,
        fecha_venta__month=hoy.month
    ).count()

    ventas_confirmadas = Venta.objects.filter(
        estado="confirmada",
        fecha_venta__year=hoy.year,
        fecha_venta__month=hoy.month
    ).count()

    # ----------------------
    # TRANSFERENCIAS (GESTORÍA)
    # ----------------------
    transferencias_pendientes = Gestoria.objects.filter(
        estado="vigente"
    ).count()

    transferencias_finalizadas = Gestoria.objects.filter(
        estado="finalizada"
    ).count()

    total_transferencias = transferencias_pendientes + transferencias_finalizadas
    cumplimiento_transferencias = (
        round((transferencias_finalizadas / total_transferencias) * 100, 0)
        if total_transferencias > 0 else 0
    )

    # ----------------------
    # ASISTENCIA (MES ACTUAL)
    # ----------------------
    faltas_mes = AsistenciaDiaria.objects.filter(
        fecha__year=hoy.year,
        fecha__month=hoy.month,
        estado__in=["falta_justificada", "falta_injustificada"]
    ).count()

    faltas_injustificadas = AsistenciaDiaria.objects.filter(
        fecha__year=hoy.year,
        fecha__month=hoy.month,
        estado="falta_injustificada"
    ).count()

    # ----------------------
    # DEUDA VENCIDA (AL DÍA)
    # ----------------------
    deudas_vencidas = CuentaCorriente.objects.filter(
        estado="deuda",
        plan_pago__cuotas__estado="pendiente",
        plan_pago__cuotas__vencimiento__lt=hoy
    ).distinct().count()

    return render(
        request,
        "reportes/web/index.html",
        {
            "page_title": "Reporte Web",
            "total_ventas": total_ventas,
            "ventas_confirmadas": ventas_confirmadas,
            "transferencias_pendientes": transferencias_pendientes,
            "cumplimiento_transferencias": cumplimiento_transferencias,
            "faltas_mes": faltas_mes,
            "faltas_injustificadas": faltas_injustificadas,
            "deudas_vencidas": deudas_vencidas,
        }
    )


@login_required
def _reporte_interno_base(request, unidad):
    # 🔑 Guardar unidad activa en sesión
    if unidad == "Hamichetti":
        request.session["unidad_activa"] = "HA"
    elif unidad == "Vamichetti":
        request.session["unidad_activa"] = "VA"

    return render(
        request,
        "reportes/interno/index.html",
        {
            "page_title": f"Reporte Interno – {unidad}",
            "unidad": unidad,
        }
    )


# ==========================================================
# REPORTE INTERNO
# ==========================================================
@login_required
def reporte_interno(request):
    # ESTE ES HAMICHETTI (el que ya existe)
    return _reporte_interno_base(request, "Hamichetti")


@login_required
def reporte_interno_vamichetti(request):
    return _reporte_interno_base(request, "Vamichetti")


# ==========================================================
# CONTROL DE STOCK
# ==========================================================
@login_required
@permission_required(
    'reportes.view_fichareporteinterno',
    raise_exception=True
)
def control_stock(request):
    # 🔄 Permite cambiar de unidad desde la misma pantalla (?unidad=HA|VA)
    unidad_param = (request.GET.get("unidad") or "").upper()
    if unidad_param in ("HA", "VA"):
        request.session["unidad_activa"] = unidad_param

    # 🔑 tomar la unidad activa desde sesión
    unidad = request.session.get("unidad_activa", "HA")
    query = request.GET.get("q", "")

    vehiculos = Vehiculo.objects.filter(
        unidad=unidad
    ).select_related(
        "ficha_reporte"
    ).order_by("-id")

    # Filtro por búsqueda
    if query:
        vehiculos = vehiculos.filter(
            Q(marca__icontains=query)
            | Q(modelo__icontains=query)
            | Q(dominio__icontains=query)
        )

    return render(
        request,
        "reportes/interno/control_stock.html",
        {
            "page_title": "Control de Stock",
            "vehiculos": vehiculos,
            "query": query,
            "unidad": unidad,
        }
    )


# ==========================================================
# EDITAR FICHA INTERNA + GASTOS
# ==========================================================
@login_required
@permission_required(
    'reportes.view_fichareporteinterno',
    raise_exception=True
)
def editar_ficha_reporte(request, vehiculo_id):
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    ficha, _ = FichaReporteInterno.objects.get_or_create(
        vehiculo=vehiculo
    )

    if request.method == "POST":
        form = FichaReporteInternoForm(request.POST, instance=ficha)
        if form.is_valid():
            form.save()
            messages.success(request, "Ficha interna guardada correctamente.")
            return redirect(
                "reportes:editar_ficha_reporte",
                vehiculo_id=vehiculo.id
            )
        else:
            messages.error(request, "No se pudo guardar la ficha. Revisá los datos ingresados.")
    else:
        form = FichaReporteInternoForm(instance=ficha)

    gasto_form = GastoReporteInternoForm()

    return render(
        request,
        "reportes/interno/editar_ficha.html",
        {
            "page_title": "Editar ficha interna",
            "form": form,
            "gasto_form": gasto_form,
            "vehiculo": vehiculo,
            "ficha": ficha,
        }
    )


# ==========================================================
# AGREGAR GASTO
# ==========================================================
@login_required
@permission_required(
    'reportes.view_fichareporteinterno',
    raise_exception=True
)
def agregar_gasto_reporte(request, ficha_id):
    ficha = get_object_or_404(FichaReporteInterno, id=ficha_id)

    if request.method == "POST":
        form = GastoReporteInternoForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.ficha = ficha
            gasto.save()
            messages.success(request, "Gasto agregado correctamente.")
        else:
            messages.error(request, "No se pudo agregar el gasto. Revisá los datos ingresados.")

    return redirect(
        "reportes:editar_ficha_reporte",
        vehiculo_id=ficha.vehiculo.id
    )


# ==========================================================
# ELIMINAR GASTO
# ==========================================================
@login_required
@permission_required(
    'reportes.view_fichareporteinterno',
    raise_exception=True
)
def eliminar_gasto_reporte(request, gasto_id):
    gasto = get_object_or_404(GastoReporteInterno, id=gasto_id)
    vehiculo_id = gasto.ficha.vehiculo.id
    gasto.delete()
    messages.success(request, "Gasto eliminado correctamente.")

    return redirect(
        "reportes:editar_ficha_reporte",
        vehiculo_id=vehiculo_id
    )


# ==========================================================
# REPORTE DE GANANCIAS (DINÁMICO)
# ==========================================================
@login_required
@permission_required(
    'reportes.view_fichareporteinterno',
    raise_exception=True
)
def reporte_ganancias(request):
    # 🔑 tomar la unidad activa desde sesión
    unidad = request.session.get("unidad_activa", "HA")

    fichas = FichaReporteInterno.objects.filter(
        vehiculo__unidad=unidad
    ).exclude(
        fecha_venta__isnull=True
    ).exclude(
        precio_compra__isnull=True,
        precio_venta__isnull=True
    )

    ganancia_total = sum(
        (f.ganancia or Decimal("0")) for f in fichas
    )

    data_mensual = {}
    for f in fichas:
        key = f.fecha_venta.strftime("%m/%Y")
        data_mensual.setdefault(key, Decimal("0"))
        data_mensual[key] += f.ganancia or Decimal("0")

    data_mensual = [
        {"periodo": k, "total": v}
        for k, v in sorted(data_mensual.items())
    ]

    data_anual = {}
    for f in fichas:
        anio = f.fecha_venta.year
        data_anual.setdefault(anio, Decimal("0"))
        data_anual[anio] += f.ganancia or Decimal("0")

    data_anual = [
        {"anio": k, "total": v}
        for k, v in sorted(data_anual.items())
    ]

    return render(
        request,
        "reportes/interno/reporte.html",
        {
            "page_title": "Reporte de Ganancias",
            "ganancia_total": ganancia_total,
            "data_mensual": data_mensual,
            "data_anual": data_anual,
        }
    )


# ==========================================================
# CIERRE DE MES (CORREGIDO)
# ==========================================================
@login_required
def cerrar_mes(request):
    hoy = date.today()

    total_facturado = (
        Venta.objects.filter(
            estado="confirmada",
            fecha_venta__year=hoy.year,
            fecha_venta__month=hoy.month
        )
        .aggregate(total=Sum("precio_venta"))["total"]
        or 0
    )

    fichas_mes = FichaReporteInterno.objects.filter(
        fecha_venta__year=hoy.year,
        fecha_venta__month=hoy.month
    )

    ganancia_mes = sum(
        (f.ganancia or Decimal("0")) for f in fichas_mes
    )

    ReporteMensual.objects.update_or_create(
        anio=hoy.year,
        mes=hoy.month,
        defaults={
            "total_facturado": total_facturado,
            "ganancia_total": ganancia_mes,
        }
    )

    return redirect("reportes:lista")


# ==========================================================
# CIERRE DE AÑO
# ==========================================================
@login_required
def cerrar_anio(request):
    hoy = date.today()

    total_facturado = (
        ReporteMensual.objects.filter(
            anio=hoy.year
        ).aggregate(total=Sum("total_facturado"))["total"] or 0
    )

    total_ganancia = (
        ReporteMensual.objects.filter(
            anio=hoy.year
        ).aggregate(total=Sum("ganancia_total"))["total"] or 0
    )

    ReporteAnual.objects.update_or_create(
        anio=hoy.year,
        defaults={
            "total_facturado": total_facturado,
            "ganancia_total": total_ganancia,
        }
    )

    return redirect("reportes:lista")
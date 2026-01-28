from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
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
def lista_reportes(request):
    reportes_mensuales = ReporteMensual.objects.all()
    reportes_anuales = ReporteAnual.objects.all()

    hoy = date.today()

    return render(
        request,
        "reportes/lista.html",
        {
            "page_title": "Reportes",
            "reportes_mensuales": reportes_mensuales,
            "reportes_anuales": reportes_anuales,
            "anio_actual": hoy.year,
            "mes_actual": hoy.month,
        }
    )


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




from django.contrib.auth.decorators import login_required

# ==========================================================
# REPORTE INTERNO (TEST)
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
    # 🔑 tomar la unidad activa desde sesión
    unidad = request.session.get("unidad_activa", "HA")

    vehiculos = Vehiculo.objects.filter(
        unidad=unidad
    ).select_related(
        "ficha_reporte"
    ).order_by("-id")

    return render(
        request,
        "reportes/interno/control_stock.html",
        {
            "page_title": "Control de Stock",
            "vehiculos": vehiculos,
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
            return redirect(
                "reportes:editar_ficha_reporte",
                vehiculo_id=vehiculo.id
            )
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

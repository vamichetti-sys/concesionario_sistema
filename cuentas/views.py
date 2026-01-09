from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from django.http import HttpResponse

# ===============================
# REPORTLAB – PDF
# ===============================
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# ===============================
# MODELOS
# ===============================
from clientes.models import Cliente
from vehiculos.models import Vehiculo, FichaVehicular
from .models import (
    CuentaCorriente,
    MovimientoCuenta,
    PlanPago,
    CuotaPlan,
    Pago,
    PagoCuota,
    BitacoraCuenta,
)

# ===============================
# FORMULARIOS
# ===============================
from .forms import PlanPagoForm, PagoForm, EditarCuotaForm


# ==========================================================
# IDENTIDAD VISUAL – COLORES CORPORATIVOS (NO TOCAR)
# ==========================================================
COLOR_AZUL = colors.HexColor("#002855")
COLOR_NARANJA = colors.HexColor("#FF6C1A")
COLOR_GRIS = colors.HexColor("#F4F6F8")
COLOR_GRIS_TEXTO = colors.HexColor("#6c757d")


# ==========================================================
# LISTA DE CUENTAS CORRIENTES
# ==========================================================
@login_required
def lista_cuentas_corrientes(request):
    cuentas_qs = (
        CuentaCorriente.objects
        .select_related('cliente', 'venta')
        .exclude(estado='cerrada')
        .order_by('-creada')
    )

    hoy = timezone.now().date()

    alertas_cuotas = (
        CuotaPlan.objects
        .filter(
            estado='pendiente',
            vencimiento__lt=hoy,
            plan__cuenta__estado__in=['al_dia', 'deuda']
        )
        .select_related(
            'plan',
            'plan__cuenta',
            'plan__cuenta__cliente',
            'plan__cuenta__venta'
        )
        .values(
            'plan__cuenta__cliente__nombre_completo',
            'plan__cuenta__venta__id'
        )
        .annotate(
            cuotas_vencidas=Count('id'),
            monto_vencido=Sum('monto')
        )
        .order_by('-cuotas_vencidas')
    )

    return render(
        request,
        'cuentas/lista_cuentas_corrientes.html',
        {
            'cuentas': cuentas_qs,
            'alertas_cuotas': alertas_cuotas,
        }
    )


# ==========================================================
# CREAR CUENTA CORRIENTE
# ==========================================================
@login_required
def crear_cuenta_corriente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    cuenta, creada = CuentaCorriente.objects.get_or_create(
        cliente=cliente,
        venta=None
    )

    if creada:
        messages.success(request, "Cuenta corriente creada correctamente.")

    return redirect('cuentas:cuenta_corriente_detalle', cuenta_id=cuenta.id)


# ==========================================================
# DETALLE DE CUENTA CORRIENTE
# ==========================================================
@login_required
def cuenta_corriente_detalle(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    plan = getattr(cuenta, 'plan_pago', None)
    cuotas = plan.cuotas.all().order_by('numero') if plan else []
    movimientos = cuenta.movimientos.order_by('-fecha')

    vehiculos = Vehiculo.objects.all()

    total_gastos_ingreso = (
        movimientos.filter(origen='permuta')
        .aggregate(total=Sum('monto'))
        .get('total') or Decimal('0')
    )

    total_gestoria = (
        movimientos.filter(origen='gestoria')
        .aggregate(total=Sum('monto'))
        .get('total') or Decimal('0')
    )

    vehiculo_permuta = (
        Vehiculo.objects
        .filter(
            movimientos_cuenta__cuenta=cuenta,
            movimientos_cuenta__origen='permuta'
        )
        .distinct()
        .first()
    )

    vehiculo_stock_id = request.GET.get("vehiculo_stock")
    vehiculo_stock = (
        Vehiculo.objects.filter(id=vehiculo_stock_id).first()
        if vehiculo_stock_id else None
    )

    vehiculo_gastos = (
        vehiculo_stock
        or vehiculo_permuta
        or (cuenta.venta.vehiculo if cuenta.venta else None)
    )

    return render(
        request,
        'cuentas/cuenta_corriente_detalle.html',
        {
            'cuenta': cuenta,
            'plan': plan,
            'cuotas': cuotas,
            'movimientos': movimientos,
            'vehiculos': vehiculos,
            'total_gastos_ingreso': total_gastos_ingreso,
            'total_gestoria': total_gestoria,
            'vehiculo_permuta': vehiculo_permuta,
            'vehiculo_gastos': vehiculo_gastos,
        }
    )
# ==========================================================
# CREAR / EDITAR PLAN DE PAGO
# ==========================================================
@login_required
@transaction.atomic
def crear_plan_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    if cuenta.estado == 'cerrada':
        messages.error(request, "La cuenta está cerrada.")
        return redirect('cuentas:cuenta_corriente_detalle', cuenta_id=cuenta.id)

    plan_existente = getattr(cuenta, 'plan_pago', None)

    if request.method == 'POST':
        form = PlanPagoForm(request.POST, instance=plan_existente)

        if form.is_valid():
            plan = form.save(commit=False)
            plan.cuenta = cuenta
            plan.estado = 'activo'
            plan.save()

            try:
                plan.cuotas.all().delete()
                fecha = plan.fecha_inicio
                for i in range(1, int(plan.cantidad_cuotas) + 1):
                    CuotaPlan.objects.create(
                        plan=plan,
                        numero=i,
                        vencimiento=fecha,
                        monto=plan.monto_cuota,
                        estado='pendiente'
                    )
                    fecha = fecha + timedelta(days=30)
            except Exception as e:
                messages.warning(
                    request,
                    f"El plan se guardó pero hubo un problema generando cuotas: {e}"
                )

            cuenta.recalcular_saldo()

            messages.success(
                request,
                "Plan de pago actualizado correctamente."
                if plan_existente else
                "Plan de pago creado correctamente."
            )

            return redirect('cuentas:cuenta_corriente_detalle', cuenta.id)

        messages.error(
            request,
            "No se pudo guardar el plan. Revisá los campos marcados."
        )
        for campo, errores in form.errors.items():
            for err in errores:
                messages.error(request, f"{campo}: {err}")

    else:
        form = PlanPagoForm(instance=plan_existente)

    return render(
        request,
        'cuentas/crear_plan_pago.html',
        {
            'cuenta': cuenta,
            'form': form,
            'plan': plan_existente
        }
    )


# ==========================================================
# REGISTRAR MOVIMIENTO / PAGO
# ==========================================================
@login_required
@transaction.atomic
def registrar_movimiento(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    plan = getattr(cuenta, 'plan_pago', None)
    cuotas = plan.cuotas.filter(estado='pendiente').order_by('numero') if plan else []

    if request.method == 'GET':
        return render(
            request,
            'cuentas/registrar_movimiento.html',
            {
                'cuenta': cuenta,
                'cuotas': cuotas,
            }
        )

    tipo = request.POST.get('tipo_movimiento')
    monto = Decimal(request.POST.get('monto'))
    forma_pago = request.POST.get('forma_pago')
    observaciones = request.POST.get('observaciones', '')

    pago = Pago.objects.create(
        cuenta=cuenta,
        forma_pago=forma_pago,
        monto_total=monto,
        observaciones=observaciones
    )

    MovimientoCuenta.objects.create(
        cuenta=cuenta,
        tipo='pago',
        monto=monto,
        descripcion=observaciones or "Pago",
        origen='manual'
    )

    plan = getattr(cuenta, 'plan_pago', None)
    if plan:
        monto_restante = monto

        cuota_inicio = None
        if tipo == 'cuota':
            cuota_id = request.POST.get('cuota_id')
            if cuota_id:
                cuota_inicio = get_object_or_404(CuotaPlan, id=cuota_id, plan=plan)

        cuotas_pendientes = (
            CuotaPlan.objects
            .filter(plan=plan, estado='pendiente')
            .order_by('numero')
        )

        if cuota_inicio:
            cuotas_pendientes = cuotas_pendientes.filter(
                numero__gte=cuota_inicio.numero
            )

        for cuota in cuotas_pendientes:
            if monto_restante <= 0:
                break

            saldo_cuota = cuota.saldo_pendiente
            if saldo_cuota <= 0:
                cuota.marcar_pagada()
                continue

            monto_a_aplicar = min(monto_restante, saldo_cuota)

            PagoCuota.objects.create(
                pago=pago,
                cuota=cuota,
                monto_aplicado=monto_a_aplicar
            )

            cuota.refresh_from_db()
            cuota.marcar_pagada()

            monto_restante -= monto_a_aplicar

        plan.verificar_finalizacion()

    cuenta.recalcular_saldo()

    return redirect('cuentas:recibo_pago_pdf', pago_id=pago.id)


# ==========================================================
# EDITAR CUOTA
# ==========================================================
@login_required
@transaction.atomic
def editar_cuota(request, cuota_id):
    cuota = get_object_or_404(CuotaPlan, id=cuota_id)
    cuenta = cuota.plan.cuenta

    if request.method == 'POST':
        form = EditarCuotaForm(request.POST, instance=cuota)
        if form.is_valid():
            form.save()

    return redirect(
        'cuentas:cuenta_corriente_detalle',
        cuenta_id=cuenta.id
    )


# ==========================================================
# PAGAR CUOTA (LEGACY)
# ==========================================================
@login_required
def pagar_cuota(request, cuota_id):
    cuota = get_object_or_404(CuotaPlan, id=cuota_id)
    return redirect(
        'cuentas:cuenta_corriente_detalle',
        cuenta_id=cuota.plan.cuenta.id
    )


# ==========================================================
# AGREGAR GASTO A CUENTA (LEGACY)
# ==========================================================
@login_required
def agregar_gasto_cuenta(request, cuenta_id):
    return redirect(
        'cuentas:cuenta_corriente_detalle',
        cuenta_id=cuenta_id
    )


# ==========================================================
# CONECTAR VEHÍCULO COMO PERMUTA (LEGACY)
# ==========================================================
@login_required
@transaction.atomic
def conectar_vehiculo_permuta(request, cuenta_id, vehiculo_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    try:
        ficha = vehiculo.ficha
        ficha.imputar_gastos_permuta_en_cuenta(cuenta)
        messages.success(
            request,
            "Vehículo vinculado y gastos imputados correctamente."
        )
    except FichaVehicular.DoesNotExist:
        messages.error(
            request,
            "El vehículo no tiene ficha vehicular."
        )

    return redirect(
        'cuentas:cuenta_corriente_detalle',
        cuenta_id=cuenta.id
    )


# ==========================================================
# RECIBO DE PAGO (PDF)
# ==========================================================
@login_required
def recibo_pago_pdf(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename=recibo_{pago.id}.pdf'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    TITULO = ParagraphStyle(
        "Titulo",
        parent=styles["Title"],
        fontSize=18,
        textColor=COLOR_AZUL,
        spaceAfter=14
    )

    SUBTITULO = ParagraphStyle(
        "Subtitulo",
        parent=styles["Normal"],
        fontSize=11,
        textColor=COLOR_NARANJA,
        spaceAfter=10
    )

    TEXTO = ParagraphStyle(
        "Texto",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=6
    )

    ETIQUETA = ParagraphStyle(
        "Etiqueta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=COLOR_GRIS_TEXTO,
        spaceAfter=2
    )

    FOOTER = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=COLOR_GRIS_TEXTO,
        alignment=1
    )

    elements = []

    elements.append(Paragraph("RECIBO DE PAGO", TITULO))
    elements.append(Paragraph("Amichetti Automotores", SUBTITULO))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Cliente", ETIQUETA))
    elements.append(Paragraph(str(cuenta.cliente), TEXTO))

    elements.append(Paragraph("Venta", ETIQUETA))
    elements.append(Paragraph(f"Venta #{cuenta.venta.id}", TEXTO))

    elements.append(Spacer(1, 12))

    tabla = Table(
        [
            ["Concepto", "Detalle"],
            ["Monto abonado", f"$ {pago.monto_total:,.0f}"],
            ["Fecha", pago.fecha.strftime("%d/%m/%Y %H:%M")],
            ["Forma de pago", pago.get_forma_pago_display()],
        ],
        colWidths=[7 * cm, 7 * cm]
    )

    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 1), (-1, -1), COLOR_GRIS),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(tabla)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Firma y aclaración", ETIQUETA))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("______________________________", TEXTO))
    elements.append(Spacer(1, 30))

    elements.append(
        Paragraph(
            "Amichetti Automotores · Rojas · Buenos Aires",
            FOOTER
        )
    )

    doc.build(elements)
    return response


# ==========================================================
# ELIMINAR PLAN DE PAGO
# ==========================================================
@login_required
@transaction.atomic
def eliminar_plan_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    if hasattr(cuenta, 'plan_pago'):
        cuenta.plan_pago.delete()
        cuenta.recalcular_saldo()
        messages.success(
            request,
            "Plan de pago eliminado correctamente."
        )

    return redirect(
        'cuentas:cuenta_corriente_detalle',
        cuenta_id=cuenta.id
    )


# ==========================================================
# ELIMINAR CUENTA CORRIENTE
# ==========================================================
@login_required
@transaction.atomic
def eliminar_cuenta_corriente(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    cuenta.delete()
    messages.success(
        request,
        "Cuenta corriente eliminada."
    )
    return redirect('cuentas:lista_cuentas_corrientes')


# ==========================================================
# HISTORIAL DE FINANCIACIÓN (FIX 404)
# ==========================================================
@login_required
def historial_financiacion(request, cuenta_id):
    cuenta = get_object_or_404(
        CuentaCorriente.objects.select_related(
            "cliente",
            "venta",
            "venta__vehiculo"
        ),
        id=cuenta_id
    )

    if cuenta.estado != "cerrada":
        messages.warning(
            request,
            "El historial de financiación solo está disponible cuando la cuenta está cerrada."
        )
        return redirect(
            "cuentas:cuenta_corriente_detalle",
            cuenta_id=cuenta.id
        )

    plan = getattr(cuenta, "plan_pago", None)
    cuotas = plan.cuotas.all().order_by("numero") if plan else []

    return render(
        request,
        "cuentas/historial_financiacion.html",
        {
            "cuenta": cuenta,
            "plan": plan,
            "cuotas": cuotas,
        }
    )
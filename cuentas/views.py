from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count
from datetime import timedelta, datetime
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.http import HttpResponse

# ===============================
# REPORTLAB – PDF
# ===============================
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
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
from .forms import (
    PlanPagoForm,
    PagoForm,
    EditarCuotaForm
)


# ==========================================================
# IDENTIDAD VISUAL – COLORES CORPORATIVOS
# ==========================================================
COLOR_AZUL       = colors.HexColor("#002855")
COLOR_NARANJA    = colors.HexColor("#FF6C1A")
COLOR_GRIS       = colors.HexColor("#F4F6F8")
COLOR_GRIS_TEXTO = colors.HexColor("#6c757d")


# ==========================================================
# HELPERS
# ==========================================================
def _parse_monto_argentino(raw: str) -> Decimal:
    if raw is None:
        raise InvalidOperation("Monto vacío")
    s = str(raw).strip()
    if not s:
        raise InvalidOperation("Monto vacío")
    s = s.replace("$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")
    else:
        if s.count(".") > 1:
            s = s.replace(".", "")
    return Decimal(s)


def _generar_pdf_recibo(pago, cuenta, concepto_extra=""):
    """
    Genera el PDF de recibo con ReportLab y devuelve un HttpResponse.
    Se usa tanto para recibos normales como para anticipo.
    """
    cliente = cuenta.cliente

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="recibo_{pago.numero_recibo}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Heading3Custom",
        fontSize=12,
        textColor=COLOR_AZUL,
        spaceAfter=4,
        fontName="Helvetica-Bold"
    ))

    elements = []

    # ----------------------------------------------------------
    # ENCABEZADO
    # ----------------------------------------------------------
    header_data = [[
        Paragraph(
            "<font color='white'><b>Amichetti Automotores</b></font><br/>"
            "<font color='#cccccc' size=9>"
            "Titular: Hugo Alberto Amichetti · CUIT: 20-13814200-1 · "
            "Tel: 2474 660154"
            "</font>",
            ParagraphStyle("H", fontSize=14, textColor=colors.white,
                           fontName="Helvetica-Bold", leading=18)
        ),
        Paragraph(
            f"<font color='white'><b>RECIBO</b></font><br/>"
            f"<font color='#cccccc' size=9>N° {pago.numero_recibo}</font>",
            ParagraphStyle("R", fontSize=12, textColor=colors.white,
                           fontName="Helvetica-Bold", alignment=2, leading=18)
        )
    ]]

    titulo_table = Table(header_data, colWidths=[12 * cm, 5 * cm])
    titulo_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_AZUL),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_AZUL]),
        ("LINEBELOW", (0, 0), (-1, -1), 4, COLOR_NARANJA),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
    ]))

    elements.append(titulo_table)
    elements.append(Spacer(1, 18))

    # ----------------------------------------------------------
    # DATOS DEL CLIENTE
    # ----------------------------------------------------------
    documento = (
        getattr(cliente, "cuit", None)
        or getattr(cliente, "dni", None)
        or "-"
    )

    elements.append(Paragraph("<b>Datos del cliente</b>", styles["Heading3Custom"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Nombre: {cliente.nombre_completo}", styles["Normal"]))
    elements.append(Paragraph(f"CUIT/DNI: {documento}", styles["Normal"]))
    elements.append(Spacer(1, 16))

    # ----------------------------------------------------------
    # DETALLE DEL PAGO
    # ----------------------------------------------------------
    elements.append(Paragraph("<b>Detalle del pago</b>", styles["Heading3Custom"]))
    elements.append(Spacer(1, 6))

    concepto = concepto_extra or pago.observaciones or "Pago"
    elements.append(Paragraph(f"Concepto: {concepto}", styles["Normal"]))
    elements.append(Paragraph(
        f"Método de pago: {pago.get_forma_pago_display()}",
        styles["Normal"]
    ))
    if pago.banco:
        elements.append(Paragraph(f"Banco: {pago.banco}", styles["Normal"]))
    if pago.numero_cheque:
        elements.append(Paragraph(f"N° cheque: {pago.numero_cheque}", styles["Normal"]))
    elements.append(Paragraph(
        f"Monto abonado: $ {pago.monto_total:,.2f}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    # ----------------------------------------------------------
    # SALDO PENDIENTE DEL PLAN
    # ----------------------------------------------------------
    plan_obj   = getattr(cuenta, "plan_pago", None)
    saldo_plan = Decimal("0")
    if plan_obj:
        saldo_plan = sum(
            (cuota.saldo_pendiente for cuota in plan_obj.cuotas.all()),
            Decimal("0")
        )

    elements.append(Paragraph(
        f"<b>Saldo pendiente del plan de pago:</b> "
        f"<font color='red'><b>$ {saldo_plan:,.2f}</b></font>",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 50))

    # ----------------------------------------------------------
    # FIRMA
    # ----------------------------------------------------------
    elements.append(Paragraph(
        "<para alignment='right'>"
        "<font color='#666666'>"
        "_____________________________<br/>"
        "Firma y aclaración"
        "</font></para>",
        styles["Normal"]
    ))

    doc.build(elements)
    return response


# ==========================================================
# LISTA DE CUENTAS CORRIENTES
# ==========================================================
@login_required
def lista_cuentas_corrientes(request):

    mostrar_cerradas = request.GET.get("mostrar_cerradas") == "1"

    cuentas_qs = (
        CuentaCorriente.objects
        .select_related("cliente", "venta")
        .order_by("-creada")
    )

    if not mostrar_cerradas:
        cuentas_qs = cuentas_qs.exclude(
            estado="cerrada",
            plan_pago__isnull=False
        )

    hoy = timezone.now().date()

    alertas_cuotas = (
        CuotaPlan.objects
        .filter(
            estado="pendiente",
            vencimiento__lt=hoy,
            plan__cuenta__estado__in=["al_dia", "deuda"]
        )
        .values(
            "plan__cuenta__cliente__nombre_completo",
            "plan__cuenta__venta__id"
        )
        .annotate(
            cuotas_vencidas=Count("id"),
            monto_vencido=Sum("monto")
        )
        .order_by("-cuotas_vencidas")
    )

    return render(
        request,
        "cuentas/lista_cuentas_corrientes.html",
        {
            "cuentas": cuentas_qs,
            "alertas_cuotas": alertas_cuotas,
            "mostrar_cerradas": mostrar_cerradas,
        }
    )


# ==========================================================
# CREAR CUENTA CORRIENTE
# (SE CREA AUTOMÁTICAMENTE AL ADJUDICAR VENTA)
# ==========================================================
@login_required
def crear_cuenta_corriente(request, cliente_id):
    messages.error(
        request,
        "La cuenta corriente se crea automáticamente al adjudicar una venta."
    )
    return redirect("clientes:detalle", cliente_id=cliente_id)


# ==========================================================
# DETALLE DE CUENTA CORRIENTE
# ==========================================================
@login_required
def cuenta_corriente_detalle(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    plan        = getattr(cuenta, "plan_pago", None)
    cuotas      = plan.cuotas.all().order_by("numero") if plan else []
    movimientos = cuenta.movimientos.order_by("-fecha")

    vehiculos = Vehiculo.objects.all()

    total_gastos_ingreso = (
        movimientos.filter(origen="permuta")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )

    total_gestoria = (
        movimientos.filter(origen="gestoria")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )

    vehiculo_permuta = (
        Vehiculo.objects
        .filter(
            movimientos_cuenta__cuenta=cuenta,
            movimientos_cuenta__origen="permuta"
        )
        .distinct()
        .first()
    )

    vehiculo_gastos = vehiculo_permuta or (
        cuenta.venta.vehiculo if cuenta.venta else None
    )

    # Deuda real = suma de saldos pendientes de cuotas
    # (refleja lo que falta pagar independientemente de los movimientos contables)
    deuda_cuotas = Decimal("0")
    if plan and plan.estado == "activo":
        deuda_cuotas = sum(
            (c.saldo_pendiente for c in cuotas),
            Decimal("0")
        )

    return render(
        request,
        "cuentas/cuenta_corriente_detalle.html",
        {
            "cuenta": cuenta,
            "plan": plan,
            "cuotas": cuotas,
            "movimientos": movimientos,
            "vehiculos": vehiculos,
            "total_gastos_ingreso": total_gastos_ingreso,
            "total_gestoria": total_gestoria,
            "vehiculo_permuta": vehiculo_permuta,
            "vehiculo_gastos": vehiculo_gastos,
            "deuda_cuotas": deuda_cuotas,
        }
    )


# ==========================================================
# CREAR / EDITAR PLAN DE PAGO
# ==========================================================
@login_required
@transaction.atomic
def crear_plan_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    if cuenta.estado == "cerrada":
        messages.error(request, "La cuenta está cerrada.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    plan_existente = getattr(cuenta, "plan_pago", None)

    if request.method == "POST":
        form = PlanPagoForm(request.POST, instance=plan_existente)

        if form.is_valid():
            plan        = form.save(commit=False)
            plan.cuenta = cuenta
            plan.estado = "activo"
            es_edicion  = plan_existente is not None

            if es_edicion:
                # Limpiar movimientos de deuda anteriores del plan
                cuenta.movimientos.filter(
                    tipo='debe',
                    descripcion__icontains='Plan de pago'
                ).delete()

            plan.save()

            if es_edicion:
                MovimientoCuenta.objects.create(
                    cuenta=cuenta,
                    descripcion=f'Plan de pago #{plan.pk} - {plan.descripcion}',
                    tipo='debe',
                    monto=plan.total_con_interes,
                    origen='venta'
                )

            # Recrear cuotas con fecha y monto individuales del POST
            plan.cuotas.all().delete()
            fecha = plan.fecha_inicio

            for i in range(1, int(plan.cantidad_cuotas) + 1):
                idx = i - 1

                fecha_raw = request.POST.get(f"form-{idx}-vencimiento", "")
                try:
                    fecha_cuota = datetime.strptime(fecha_raw, "%Y-%m-%d").date() if fecha_raw else fecha
                except ValueError:
                    fecha_cuota = fecha

                monto_raw = request.POST.get(f"form-{idx}-monto", "")
                try:
                    monto_cuota = Decimal(monto_raw) if monto_raw else plan.monto_cuota
                    if monto_cuota <= 0:
                        monto_cuota = plan.monto_cuota
                except Exception:
                    monto_cuota = plan.monto_cuota

                CuotaPlan.objects.create(
                    plan=plan,
                    numero=i,
                    vencimiento=fecha_cuota,
                    monto=monto_cuota,
                    estado="pendiente"
                )
                fecha += timedelta(days=30)

            cuenta.recalcular_saldo()

            # --------------------------------------------------
            # ANTICIPO: si hay anticipo > 0 crear recibo automático
            # --------------------------------------------------
            anticipo = plan.anticipo or Decimal("0")
            if anticipo > 0 and not es_edicion:
                forma_pago_anticipo = request.POST.get("forma_pago_anticipo", "efectivo")
                banco_anticipo      = request.POST.get("banco_anticipo", "")
                cheque_anticipo     = request.POST.get("numero_cheque_anticipo", "")

                # Registrar el haber del anticipo en la cuenta
                MovimientoCuenta.objects.create(
                    cuenta=cuenta,
                    descripcion=f"Anticipo plan de pago #{plan.pk} - {plan.descripcion}",
                    tipo="haber",
                    monto=anticipo,
                    origen="venta"
                )
                cuenta.recalcular_saldo()

                # Crear objeto Pago para el recibo
                pago_anticipo = Pago.objects.create(
                    cuenta=cuenta,
                    forma_pago=forma_pago_anticipo,
                    banco=banco_anticipo,
                    numero_cheque=cheque_anticipo,
                    monto_total=anticipo,
                    observaciones=f"Anticipo plan de pago - {plan.descripcion}",
                    saldo_anterior=cuenta.saldo + anticipo,
                    saldo_posterior=cuenta.saldo,
                )

                messages.success(
                    request,
                    f"Plan guardado. Anticipo de $ {anticipo:,.0f} registrado. Redirigiendo al recibo..."
                )
                return redirect("cuentas:recibo_pago_pdf", pago_id=pago_anticipo.id)

            messages.success(request, "Plan de pago guardado correctamente.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta.id)

    else:
        form = PlanPagoForm(instance=plan_existente)

    return render(
        request,
        "cuentas/crear_plan_pago.html",
        {"cuenta": cuenta, "form": form, "plan": plan_existente}
    )


# ==========================================================
# REGISTRAR MOVIMIENTO
# ==========================================================
@login_required
@transaction.atomic
def registrar_movimiento(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    plan   = getattr(cuenta, "plan_pago", None)
    cuotas = plan.cuotas.filter(estado="pendiente").order_by("numero") if plan else []

    if request.method == "POST":
        tipo_movimiento = request.POST.get("tipo_movimiento")
        monto_raw       = request.POST.get("monto")
        forma_pago      = request.POST.get("forma_pago")
        observaciones   = request.POST.get("observaciones", "")
        cuota_id        = request.POST.get("cuota_id")

        try:
            monto = _parse_monto_argentino(monto_raw)
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect("cuentas:registrar_movimiento", cuenta_id=cuenta.id)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a 0.")
            return redirect("cuentas:registrar_movimiento", cuenta_id=cuenta.id)

        saldo_anterior = cuenta.saldo

        pago = Pago.objects.create(
            cuenta=cuenta,
            monto_total=monto,
            forma_pago=forma_pago,
            observaciones=observaciones,
            saldo_anterior=saldo_anterior,
        )

        if tipo_movimiento == "cuota" and cuota_id:
            cuota = get_object_or_404(CuotaPlan, id=cuota_id, plan__cuenta=cuenta)
            PagoCuota.objects.create(pago=pago, cuota=cuota, monto_aplicado=monto)
            cuota.marcar_pagada()
        else:
            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                descripcion=f"Pago ({forma_pago}) {observaciones}".strip(),
                tipo="haber",
                monto=monto,
                origen="manual"
            )
            cuenta.recalcular_saldo()

        pago.saldo_posterior = cuenta.saldo
        pago.save(update_fields=["saldo_posterior"])

        messages.success(request, "Pago registrado correctamente.")
        return redirect("cuentas:recibo_pago_pdf", pago_id=pago.id)

    return render(
        request,
        "cuentas/registrar_movimiento.html",
        {"cuenta": cuenta, "cuotas": cuotas}
    )


# ==========================================================
# REGISTRAR PAGO DE GESTORÍA
# ==========================================================
@login_required
@transaction.atomic
def registrar_pago_gestoria(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    total_gestoria = (
        cuenta.movimientos.filter(origen="gestoria")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )

    if request.method == "POST":
        monto_raw     = request.POST.get("monto")
        observaciones = request.POST.get("observaciones", "")

        try:
            monto = _parse_monto_argentino(monto_raw)
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect("cuentas:registrar_pago_gestoria", cuenta_id=cuenta.id)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a 0.")
            return redirect("cuentas:registrar_pago_gestoria", cuenta_id=cuenta.id)

        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            descripcion=f"Pago gestoría {observaciones}".strip(),
            tipo="haber",
            monto=monto,
            origen="gestoria"
        )
        cuenta.recalcular_saldo()

        messages.success(request, "Pago de gestoría registrado.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    return render(
        request,
        "cuentas/registrar_pago_gestoria.html",
        {"cuenta": cuenta, "total_gestoria": total_gestoria}
    )


# ==========================================================
# RECIBO DE PAGO (PDF con ReportLab)
# ==========================================================
@login_required
def recibo_pago_pdf(request, pago_id):
    pago   = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta
    return _generar_pdf_recibo(pago, cuenta)


# ==========================================================
# EDITAR CUOTA
# ==========================================================
@login_required
@transaction.atomic
def editar_cuota(request, cuota_id):
    cuota = get_object_or_404(CuotaPlan, id=cuota_id)

    form = EditarCuotaForm(
        request.POST or None,
        instance=cuota
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cuota actualizada correctamente.")

    return redirect(
        "cuentas:cuenta_corriente_detalle",
        cuenta_id=cuota.plan.cuenta.id
    )


# ==========================================================
# CONECTAR VEHÍCULO COMO PERMUTA
# ==========================================================
@login_required
@transaction.atomic
def conectar_vehiculo_permuta(request, cuenta_id, vehiculo_id):
    cuenta   = get_object_or_404(CuentaCorriente, id=cuenta_id)
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    ficha = vehiculo.ficha
    ficha.imputar_gastos_permuta_en_cuenta(cuenta)

    messages.success(request, "Vehículo vinculado correctamente.")
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)


# ==========================================================
# ELIMINAR PLAN DE PAGO
# Borra el plan, todas sus cuotas, los pagos asociados
# y los movimientos contables que generó.
# ==========================================================
@login_required
@transaction.atomic
def eliminar_plan_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    plan = getattr(cuenta, "plan_pago", None)
    if not plan:
        messages.error(request, "La cuenta no tiene plan de pago.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    # 1. Borrar movimientos de DEBE generados por este plan
    cuenta.movimientos.filter(
        tipo="debe",
        descripcion__icontains="Plan de pago"
    ).delete()

    # 2. Borrar movimientos de HABER de pagos de cuotas (origen venta)
    cuenta.movimientos.filter(
        tipo="haber",
        origen="venta"
    ).delete()

    # 3. Borrar movimientos de anticipo si los hubiera
    cuenta.movimientos.filter(
        tipo="haber",
        descripcion__icontains="Anticipo plan"
    ).delete()

    # 4. Borrar objetos Pago vinculados a la cuenta
    #    (PagoCuota se borra por CASCADE desde Pago)
    Pago.objects.filter(cuenta=cuenta).delete()

    # 5. Borrar el plan — las CuotaPlan se borran por CASCADE
    plan.delete()

    # 6. Recalcular saldo limpio
    cuenta.recalcular_saldo()

    messages.success(request, "Plan de pago eliminado correctamente.")
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)


# ==========================================================
# ELIMINAR CUENTA CORRIENTE
# ==========================================================
@login_required
@transaction.atomic
def eliminar_cuenta_corriente(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    from boletos.models import BoletoCompraventa
    BoletoCompraventa.objects.filter(cuenta_corriente=cuenta).update(cuenta_corriente=None)

    cuenta.delete()
    messages.success(request, "Cuenta corriente eliminada correctamente.")
    return redirect("cuentas:lista_cuentas_corrientes")


# ==========================================================
# PAGAR CUOTA (LEGACY)
# ==========================================================
@login_required
def pagar_cuota(request, cuota_id):
    cuota = get_object_or_404(CuotaPlan, id=cuota_id)
    return redirect(
        "cuentas:cuenta_corriente_detalle",
        cuenta_id=cuota.plan.cuenta.id
    )


# ==========================================================
# AGREGAR GASTO A CUENTA (LEGACY)
# ==========================================================
@login_required
def agregar_gasto_cuenta(request, cuenta_id):
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta_id)


# ==========================================================
# HISTORIAL DE FINANCIACIÓN
# ==========================================================
@login_required
def historial_financiacion(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    plan   = getattr(cuenta, "plan_pago", None)
    cuotas = plan.cuotas.all() if plan else []

    return render(
        request,
        "cuentas/historial_financiacion.html",
        {"cuenta": cuenta, "plan": plan, "cuotas": cuotas}
    )


# ==========================================================
# CERRAR CUENTA CORRIENTE
# ==========================================================
@login_required
@transaction.atomic
def cerrar_cuenta_corriente(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    if not cuenta.venta or cuenta.venta.estado != "revertida":
        messages.error(
            request,
            "Solo se puede cerrar la cuenta si la venta fue revertida."
        )
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    try:
        cuenta.cerrar()
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    messages.success(request, "Cuenta corriente cerrada correctamente.")
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

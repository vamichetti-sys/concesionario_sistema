from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Coalesce
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
from vehiculos.models import Vehiculo, FichaVehicular, PagoGastoIngreso
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


def _generar_pdf_recibo(pago, cuenta, concepto_extra="", modo_saldo="completo"):
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
    # SALDO PENDIENTE (según modo elegido)
    # ----------------------------------------------------------
    if modo_saldo != "oculto":
        plan_obj   = getattr(cuenta, "plan_pago", None)
        saldo_plan = Decimal("0")
        if plan_obj:
            saldo_plan = sum(
                (cuota.saldo_pendiente for cuota in plan_obj.cuotas.all()),
                Decimal("0")
            )

        if modo_saldo == "completo":
            # Gestoría
            gestoria_debe = (
                cuenta.movimientos.filter(origen="gestoria", tipo="debe")
                .aggregate(total=Sum("monto")).get("total") or Decimal("0")
            )
            gestoria_haber = (
                cuenta.movimientos.filter(origen="gestoria", tipo="haber")
                .aggregate(total=Sum("monto")).get("total") or Decimal("0")
            )
            total_gestoria = max(gestoria_debe - gestoria_haber, Decimal("0"))

            # Gastos de ingreso pendientes
            saldo_gastos = Decimal("0")
            vehiculo_permuta = (
                Vehiculo.objects.filter(
                    movimientos_cuenta__cuenta=cuenta,
                    movimientos_cuenta__origen="permuta"
                ).distinct().first()
            )
            if vehiculo_permuta:
                try:
                    saldo_gastos = vehiculo_permuta.ficha.saldo_total_gastos()
                except FichaVehicular.DoesNotExist:
                    pass

            deuda_total = saldo_plan + total_gestoria + saldo_gastos

            elements.append(Paragraph("<b>Estado de cuenta</b>", styles["Heading3Custom"]))
            elements.append(Spacer(1, 6))
            if saldo_plan > 0:
                elements.append(Paragraph(f"Plan de pago: $ {saldo_plan:,.2f}", styles["Normal"]))
            if total_gestoria > 0:
                elements.append(Paragraph(f"Gestoría: $ {total_gestoria:,.2f}", styles["Normal"]))
            if saldo_gastos > 0:
                elements.append(Paragraph(f"Gastos de ingreso: $ {saldo_gastos:,.2f}", styles["Normal"]))
            elements.append(Spacer(1, 4))
            elements.append(Paragraph(
                f"<b>Deuda total pendiente:</b> "
                f"<font color='red'><b>$ {deuda_total:,.2f}</b></font>",
                styles["Normal"]
            ))

        else:  # modo_saldo == "plan"
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
    tab = request.GET.get("tab", "deuda")  # 'deuda' o 'al_dia'
    query = request.GET.get("q", "").strip()

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

    if query:
        cuentas_qs = cuentas_qs.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(venta__id__icontains=query)
        )

    # Separar en con deuda / al día según deuda_total_real
    cuentas_con_deuda = []
    cuentas_al_dia = []
    for c in cuentas_qs:
        if c.deuda_total_real > 0:
            cuentas_con_deuda.append(c)
        else:
            cuentas_al_dia.append(c)

    cuentas_mostradas = cuentas_al_dia if tab == "al_dia" else cuentas_con_deuda

    hoy = timezone.now().date()

    alertas_cuotas = (
        CuotaPlan.objects
        .filter(
            estado="pendiente",
            vencimiento__lt=hoy,
            plan__cuenta__estado__in=["al_dia", "deuda"]
        )
        .annotate(
            total_pagado=Coalesce(Sum("pagos__monto_aplicado"), Decimal("0"))
        )
        .filter(monto__gt=F("total_pagado"))
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
            "cuentas": cuentas_mostradas,
            "cuentas_con_deuda_count": len(cuentas_con_deuda),
            "cuentas_al_dia_count": len(cuentas_al_dia),
            "tab_actual": tab,
            "query": query,
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

    gestoria_debe = (
        movimientos.filter(origen="gestoria", tipo="debe")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )
    gestoria_haber = (
        movimientos.filter(origen="gestoria", tipo="haber")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )
    total_gestoria = gestoria_debe - gestoria_haber

    vehiculos_permuta = list(
        Vehiculo.objects
        .filter(
            movimientos_cuenta__cuenta=cuenta,
            movimientos_cuenta__origen="permuta"
        )
        .distinct()
    )

    # Compatibilidad: primer vehículo (algunos templates/recibos lo usan)
    vehiculo_permuta = vehiculos_permuta[0] if vehiculos_permuta else None
    vehiculo_gastos = vehiculo_permuta

    # Gastos de ingreso: detalle por vehículo
    total_gastos_ingreso = Decimal("0")
    saldo_gastos_ingreso = Decimal("0")
    gastos_detalle = []          # plano (legacy / para PDF)
    vehiculos_gastos = []        # agrupado por vehículo (para template)

    CONCEPTOS_KEYS = {
        "Formulario 08": "f08",
        "Informes": "informes",
        "Patentes": "patentes",
        "Infracciones": "infracciones",
        "Verificación": "verificacion",
        "Autopartes": "autopartes",
        "VTV": "vtv",
        "R541": "r541",
        "Firmas": "firmas",
    }

    for veh in vehiculos_permuta:
        try:
            ficha_v = veh.ficha
        except FichaVehicular.DoesNotExist:
            continue
        items_veh = []
        total_veh = Decimal("0")
        saldo_veh = Decimal("0")
        for concepto, monto in ficha_v.mapa_gastos_ingreso().items():
            if not monto or Decimal(monto) <= 0:
                continue
            monto_dec = Decimal(monto)
            key = CONCEPTOS_KEYS.get(concepto, concepto)
            total_pagado = (
                PagoGastoIngreso.objects.filter(
                    vehiculo=veh,
                    concepto__in=[concepto, key],
                ).aggregate(total=Sum("monto"))["total"]
                or Decimal("0")
            )
            saldo = monto_dec - Decimal(total_pagado)
            item = {
                "concepto": concepto,
                "monto": monto_dec,
                "total_pagado": total_pagado,
                "saldo": saldo,
                "pagado": saldo <= 0,
                "vehiculo": veh,
            }
            items_veh.append(item)
            gastos_detalle.append(item)
            total_veh += monto_dec
            total_gastos_ingreso += monto_dec
            if saldo > 0:
                saldo_veh += saldo
                saldo_gastos_ingreso += saldo
        if items_veh:
            vehiculos_gastos.append({
                "vehiculo": veh,
                "items": items_veh,
                "total": total_veh,
                "saldo": saldo_veh,
            })

    # Deuda real = suma de saldos pendientes de cuotas
    # (refleja lo que falta pagar independientemente de los movimientos contables)
    deuda_cuotas = Decimal("0")
    if plan and plan.estado == "activo":
        deuda_cuotas = sum(
            (c.saldo_pendiente for c in cuotas),
            Decimal("0")
        )

    # Deuda total = saldo de cuotas + gestoría pendiente + gastos de ingreso pendientes
    deuda_total = deuda_cuotas + max(total_gestoria, Decimal("0")) + saldo_gastos_ingreso

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
            "saldo_gastos_ingreso": saldo_gastos_ingreso,
            "gastos_detalle": gastos_detalle,
            "total_gestoria": total_gestoria,
            "gestoria_debe": gestoria_debe,
            "gestoria_haber": gestoria_haber,
            "vehiculo_permuta": vehiculo_permuta,
            "vehiculo_gastos": vehiculo_gastos,
            "vehiculos_permuta": vehiculos_permuta,
            "vehiculos_gastos": vehiculos_gastos,
            "deuda_cuotas": deuda_cuotas,
            "deuda_total": deuda_total,
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
                except (ValueError, ArithmeticError):
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
        except (ValueError, InvalidOperation):
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
        elif plan and plan.cuotas.filter(estado="pendiente").exists():
            # Vincular automáticamente a cuotas pendientes (empezando por la más antigua)
            restante = monto
            for cuota in plan.cuotas.filter(estado="pendiente").order_by("numero"):
                if restante <= 0:
                    break
                saldo_cuota = cuota.saldo_pendiente
                if saldo_cuota <= 0:
                    continue
                aplicar = min(restante, saldo_cuota)
                PagoCuota.objects.create(pago=pago, cuota=cuota, monto_aplicado=aplicar)
                cuota.marcar_pagada()
                restante -= aplicar
        else:
            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                descripcion=f"Pago ({forma_pago}) {observaciones}".strip(),
                tipo="haber",
                monto=monto,
                origen="manual",
                pago=pago,
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

    gest_debe = (
        cuenta.movimientos.filter(origen="gestoria", tipo="debe")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )
    gest_haber = (
        cuenta.movimientos.filter(origen="gestoria", tipo="haber")
        .aggregate(total=Sum("monto"))
        .get("total") or Decimal("0")
    )
    total_gestoria = gest_debe - gest_haber

    if request.method == "POST":
        monto_raw     = request.POST.get("monto")
        observaciones = request.POST.get("observaciones", "")

        try:
            monto = _parse_monto_argentino(monto_raw)
        except (ValueError, InvalidOperation):
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
    modo_saldo = request.GET.get("saldo", "completo")
    return _generar_pdf_recibo(pago, cuenta, modo_saldo=modo_saldo)


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

    ya_vinculado = cuenta.movimientos.filter(
        origen="permuta", vehiculo=vehiculo
    ).exists()

    ficha = vehiculo.ficha
    ficha.imputar_gastos_permuta_en_cuenta(cuenta)
    cuenta.recalcular_saldo()

    if ya_vinculado:
        messages.info(request, f"El vehículo {vehiculo} ya estaba vinculado.")
    else:
        messages.success(request, f"Vehículo {vehiculo} vinculado correctamente.")
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


# ==========================================================
# EDITAR PAGO (solo metadatos: forma, banco, cheque, observaciones)
# ==========================================================
@login_required
@transaction.atomic
def editar_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta

    if request.method == "POST":
        forma_pago = request.POST.get("forma_pago", pago.forma_pago)
        banco = request.POST.get("banco", "").strip()
        numero_cheque = request.POST.get("numero_cheque", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        pago.forma_pago = forma_pago
        pago.banco = banco
        pago.numero_cheque = numero_cheque
        pago.observaciones = observaciones
        pago.save(update_fields=[
            "forma_pago", "banco", "numero_cheque", "observaciones"
        ])

        messages.success(request, f"Pago {pago.numero_recibo} actualizado.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    return render(request, "cuentas/editar_pago.html", {
        "pago": pago,
        "cuenta": cuenta,
    })


# ==========================================================
# ELIMINAR PAGO (revierte todo)
# ==========================================================
@login_required
@transaction.atomic
def eliminar_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta

    if request.method != "POST":
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    cuotas_afectadas = list(
        CuotaPlan.objects.filter(pagos__pago=pago).distinct()
    )

    pago.movimientos_creados.all().delete()
    pago.delete()

    for cuota in cuotas_afectadas:
        if cuota.saldo_pendiente > 0 and cuota.estado == "pagada":
            cuota.estado = "pendiente"
            cuota.save(update_fields=["estado"])

    plan = getattr(cuenta, "plan_pago", None)
    if plan and plan.estado == "finalizado":
        if plan.cuotas.filter(estado="pendiente").exists():
            plan.estado = "activo"
            plan.save(update_fields=["estado"])

    cuenta.recalcular_saldo()

    messages.success(request, "Pago eliminado correctamente.")
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)


# ==========================================================
# DESVINCULAR VEHÍCULO DE PERMUTA (uno específico)
# ==========================================================
@login_required
@transaction.atomic
def desvincular_vehiculo_permuta(request, cuenta_id, vehiculo_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    if request.method != "POST":
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    movs = cuenta.movimientos.filter(origen="permuta", vehiculo_id=vehiculo_id)
    if not movs.exists():
        messages.info(request, "Ese vehículo no estaba vinculado a esta cuenta.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    nombre = str(movs.first().vehiculo)
    movs.delete()
    cuenta.recalcular_saldo()
    messages.success(request, f"Vehículo {nombre} desvinculado correctamente.")
    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)


# ==========================================================
# PDF: PLAN DE PAGO
# ==========================================================
@login_required
def plan_pago_pdf(request, cuenta_id):
    from io import BytesIO
    from reportlab.lib.enums import TA_CENTER

    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    plan = getattr(cuenta, "plan_pago", None)

    if not plan:
        messages.error(request, "Esta cuenta no tiene plan de pago.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    cliente = cuenta.cliente
    cuotas = plan.cuotas.all().order_by("numero")

    total_monto = sum((c.monto for c in cuotas), Decimal("0"))
    total_pagado = sum((c.total_pagado for c in cuotas), Decimal("0"))
    total_saldo = sum((c.saldo_pendiente for c in cuotas), Decimal("0"))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, alignment=TA_CENTER, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER, spaceAfter=14)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=11, textColor=colors.HexColor("#1e3a5f"), spaceBefore=10, spaceAfter=6)
    normal = styles["Normal"]

    elements = []
    elements.append(Paragraph("AMICHETTI AUTOMOTORES", H1))
    elements.append(Paragraph(
        f"Plan de pago — Emitido el {timezone.localdate().strftime('%d/%m/%Y')}",
        sub
    ))

    documento = getattr(cliente, "dni_cuit", None) or "-"
    elements.append(Paragraph("<b>Cliente</b>", h3))
    info_cliente = [
        [Paragraph("<b>Nombre:</b>", normal), Paragraph(cliente.nombre_completo or "-", normal)],
        [Paragraph("<b>DNI / CUIT:</b>", normal), Paragraph(str(documento), normal)],
    ]
    if getattr(cliente, "direccion", None):
        info_cliente.append([Paragraph("<b>Domicilio:</b>", normal), Paragraph(cliente.direccion, normal)])
    if getattr(cliente, "telefono", None):
        info_cliente.append([Paragraph("<b>Teléfono:</b>", normal), Paragraph(cliente.telefono, normal)])

    t_cli = Table(info_cliente, colWidths=[3.5 * cm, 13 * cm])
    t_cli.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_cli)

    elements.append(Paragraph("<b>Detalle del plan</b>", h3))
    info_plan = [
        ["Descripción", plan.descripcion or "-"],
        ["Tipo de plan", plan.get_tipo_plan_display()],
        ["Moneda", plan.get_moneda_display()],
        ["Fecha de inicio", plan.fecha_inicio.strftime("%d/%m/%Y") if plan.fecha_inicio else "-"],
        ["Cantidad de cuotas", str(plan.cantidad_cuotas)],
        ["Monto financiado", f"$ {plan.monto_financiado:,.2f}"],
    ]
    if plan.anticipo and plan.anticipo > 0:
        info_plan.append(["Anticipo", f"$ {plan.anticipo:,.2f}"])
    if plan.interes_financiacion and plan.interes_financiacion > 0:
        info_plan.append(["Interés de financiación", f"{plan.interes_financiacion}%"])
        info_plan.append(["Total con interés", f"$ {plan.total_con_interes:,.2f}"])
    if plan.interes_mora_mensual and plan.interes_mora_mensual > 0:
        info_plan.append(["Interés mora mensual", f"{plan.interes_mora_mensual}%"])
    info_plan.append(["Estado", plan.get_estado_display()])

    t_plan = Table(info_plan, colWidths=[5 * cm, 11.5 * cm])
    t_plan.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_plan)

    elements.append(Paragraph("<b>Cuotas</b>", h3))

    data = [["N°", "Vencimiento", "Monto", "Pagado", "Saldo", "Estado"]]
    hoy = timezone.localdate()
    for c in cuotas:
        if c.estado == "pagada":
            estado_txt = "Pagada"
        elif c.vencimiento and c.vencimiento < hoy and c.saldo_pendiente > 0:
            estado_txt = "Vencida"
        else:
            estado_txt = "Pendiente"
        data.append([
            str(c.numero),
            c.vencimiento.strftime("%d/%m/%Y") if c.vencimiento else "-",
            f"$ {c.monto:,.2f}",
            f"$ {c.total_pagado:,.2f}",
            f"$ {c.saldo_pendiente:,.2f}",
            estado_txt,
        ])

    data.append([
        "", "TOTAL",
        f"$ {total_monto:,.2f}",
        f"$ {total_pagado:,.2f}",
        f"$ {total_saldo:,.2f}",
        "",
    ])

    t_cuotas = Table(
        data,
        colWidths=[1.2 * cm, 3 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 2.7 * cm],
        repeatRows=1,
    )
    t_cuotas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (5, 0), (5, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_cuotas)

    # ----------------------------------------------------------
    # GESTORÍA
    # ----------------------------------------------------------
    gestoria_debe = (
        cuenta.movimientos.filter(origen="gestoria", tipo="debe")
        .aggregate(total=Sum("monto")).get("total") or Decimal("0")
    )
    gestoria_haber = (
        cuenta.movimientos.filter(origen="gestoria", tipo="haber")
        .aggregate(total=Sum("monto")).get("total") or Decimal("0")
    )
    gestoria_saldo = max(gestoria_debe - gestoria_haber, Decimal("0"))

    if gestoria_debe > 0:
        elements.append(Paragraph("<b>Gestoría</b>", h3))
        data_gest = [
            ["Concepto", "Monto"],
            ["Debe (deuda inicial)", f"$ {gestoria_debe:,.2f}"],
            ["Haber (pagos realizados)", f"$ {gestoria_haber:,.2f}"],
            ["Saldo pendiente", f"$ {gestoria_saldo:,.2f}"],
        ]
        t_gest = Table(data_gest, colWidths=[10 * cm, 6.5 * cm])
        t_gest.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_gest)

    # ----------------------------------------------------------
    # GASTOS DEL VEHÍCULO VINCULADO (PERMUTA)
    # ----------------------------------------------------------
    vehiculo_permuta = (
        Vehiculo.objects.filter(
            movimientos_cuenta__cuenta=cuenta,
            movimientos_cuenta__origen="permuta",
        ).distinct().first()
    )

    gastos_total = Decimal("0")
    gastos_pagado = Decimal("0")
    gastos_saldo = Decimal("0")
    gastos_filas = []

    if vehiculo_permuta:
        try:
            ficha_v = vehiculo_permuta.ficha
            CONCEPTOS_KEYS = {
                "Formulario 08": "f08", "Informes": "informes", "Patentes": "patentes",
                "Infracciones": "infracciones", "Verificación": "verificacion",
                "Autopartes": "autopartes", "VTV": "vtv", "R541": "r541", "Firmas": "firmas",
            }
            for concepto, monto in ficha_v.mapa_gastos_ingreso().items():
                if not monto or Decimal(monto) <= 0:
                    continue
                monto_dec = Decimal(monto)
                key = CONCEPTOS_KEYS.get(concepto, concepto)
                pagado = (
                    PagoGastoIngreso.objects.filter(
                        vehiculo=vehiculo_permuta,
                        concepto__in=[concepto, key],
                    ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
                )
                saldo_g = max(monto_dec - Decimal(pagado), Decimal("0"))
                gastos_total += monto_dec
                gastos_pagado += Decimal(pagado)
                gastos_saldo += saldo_g
                gastos_filas.append([
                    concepto,
                    f"$ {monto_dec:,.2f}",
                    f"$ {Decimal(pagado):,.2f}",
                    f"$ {saldo_g:,.2f}",
                    "Pagado" if saldo_g <= 0 else "Pendiente",
                ])
        except FichaVehicular.DoesNotExist:
            pass

    if gastos_filas:
        titulo_gastos = (
            f"<b>Gastos del vehículo vinculado · "
            f"{vehiculo_permuta.marca} {vehiculo_permuta.modelo} ({vehiculo_permuta.dominio})</b>"
        )
        elements.append(Paragraph(titulo_gastos, h3))

        data_gastos = [["Concepto", "Monto", "Pagado", "Saldo", "Estado"]]
        data_gastos.extend(gastos_filas)
        data_gastos.append([
            "TOTAL",
            f"$ {gastos_total:,.2f}",
            f"$ {gastos_pagado:,.2f}",
            f"$ {gastos_saldo:,.2f}",
            "",
        ])

        t_gastos = Table(
            data_gastos,
            colWidths=[5 * cm, 3 * cm, 3 * cm, 3 * cm, 2.5 * cm],
            repeatRows=1,
        )
        t_gastos.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (3, -1), "RIGHT"),
            ("ALIGN", (4, 0), (4, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_gastos)

    # ----------------------------------------------------------
    # RESUMEN FINAL
    # ----------------------------------------------------------
    deuda_total = total_saldo + gestoria_saldo + gastos_saldo

    elements.append(Spacer(1, 18))
    elements.append(Paragraph("<b>Resumen de saldos pendientes</b>", h3))
    resumen_data = [
        ["Plan de pago", f"$ {total_saldo:,.2f}"],
    ]
    if gestoria_debe > 0:
        resumen_data.append(["Gestoría", f"$ {gestoria_saldo:,.2f}"])
    if gastos_filas:
        resumen_data.append(["Gastos del vehículo", f"$ {gastos_saldo:,.2f}"])
    resumen_data.append(["DEUDA TOTAL PENDIENTE", f"$ {deuda_total:,.2f}"])

    t_resumen = Table(resumen_data, colWidths=[10 * cm, 6.5 * cm])
    t_resumen.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fee2e2") if deuda_total > 0 else colors.HexColor("#dcfce7")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#991b1b") if deuda_total > 0 else colors.HexColor("#166534")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_resumen)

    doc.build(elements)
    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="plan_pago_{cuenta.id}_{cliente.nombre_completo or "cliente"}.pdf"'
    )
    return response

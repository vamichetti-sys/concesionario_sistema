from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count
from datetime import timedelta
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
COLOR_AZUL = colors.HexColor("#002855")
COLOR_NARANJA = colors.HexColor("#FF6C1A")
COLOR_GRIS = colors.HexColor("#F4F6F8")
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

    # 🔒 Comportamiento original:
    # ocultar cuentas cerradas,
    # PERO mostrar las cerradas que aún NO tienen plan de pago
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
# (DESHABILITADO: SE CREA AUTOMÁTICAMENTE AL ADJUDICAR VENTA)
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

    plan = getattr(cuenta, "plan_pago", None)
    cuotas = plan.cuotas.all().order_by("numero") if plan else []
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
            plan = form.save(commit=False)
            plan.cuenta = cuenta
            plan.estado = "activo"
            plan.save()

            plan.cuotas.all().delete()
            fecha = plan.fecha_inicio

            for i in range(1, int(plan.cantidad_cuotas) + 1):
                CuotaPlan.objects.create(
                    plan=plan,
                    numero=i,
                    vencimiento=fecha,
                    monto=plan.monto_cuota,
                    estado="pendiente"
                )
                fecha += timedelta(days=30)

            cuenta.recalcular_saldo()
            messages.success(request, "Plan de pago guardado.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta.id)

    else:
        form = PlanPagoForm(instance=plan_existente)

    return render(
        request,
        "cuentas/crear_plan_pago.html",
        {"cuenta": cuenta, "form": form, "plan": plan_existente}
    )


# ==========================================================
# REGISTRAR MOVIMIENTO / PAGO  ✅ FIX DEFINITIVO (3 TIPOS)
# - cuota   -> elige cuota e imputa desde esa cuota
# - unico   -> NO elige cuotas, resta un monto único
# - cheque  -> pide banco + nro cheque + monto (NO elige cuotas)
# ==========================================================
@login_required
@transaction.atomic
def registrar_movimiento(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    plan = getattr(cuenta, "plan_pago", None)

    # ===============================
    # GET: mostrar formulario
    # ===============================
    if request.method == "GET":
        cuotas = []

        if plan:
            for cuota in plan.cuotas.all().order_by("numero"):
                saldo = cuota.saldo_pendiente
                try:
                    saldo = Decimal(saldo) if saldo is not None else Decimal("0")
                except Exception:
                    saldo = Decimal("0")

                if saldo > 0:
                    cuota.saldo_actual = saldo  # atributo temporal
                    cuotas.append(cuota)

        return render(
            request,
            "cuentas/registrar_movimiento.html",
            {
                "cuenta": cuenta,
                "cuotas": cuotas,
            }
        )

    # ===============================
    # POST: leer datos
    # ===============================
    tipo = (request.POST.get("tipo_movimiento") or "").strip()
    forma_pago = (request.POST.get("forma_pago") or "").strip()
    observaciones = (request.POST.get("observaciones") or "").strip()

    if tipo not in ["cuota", "unico", "cheque"]:
        messages.error(request, "Seleccioná un tipo de pago válido.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    if not forma_pago:
        messages.error(request, "Seleccioná la forma de pago.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    try:
        monto = _parse_monto_argentino(request.POST.get("monto"))
    except Exception:
        messages.error(request, "Monto inválido.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    if monto <= 0:
        messages.error(request, "El monto debe ser mayor a 0.")
        return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

    # ===============================
    # Datos extra para CHEQUE
    # ===============================
    numero_cheque = (request.POST.get("numero_cheque") or "").strip()
    banco = (request.POST.get("banco") or "").strip()

    if tipo == "cheque":
        if not banco or not numero_cheque:
            messages.error(request, "Para cheque: ingresá banco y número de cheque.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

        extra = f"Cheque N° {numero_cheque} - Banco {banco}"
        observaciones = f"{observaciones} | {extra}" if observaciones else extra

    # ===============================
    # CAPTURAR SALDO ANTES DEL PAGO
    # ===============================
    saldo_anterior = cuenta.saldo

    # ===============================
    # Crear PAGO
    # ===============================
    pago = Pago.objects.create(
        cuenta=cuenta,
        forma_pago=forma_pago,
        monto_total=monto,
        observaciones=observaciones,
        saldo_anterior=saldo_anterior
    )

    # ===============================
    # Movimiento base
    # ===============================
    if tipo == "cuota":
        descripcion_mov = observaciones or "Pago cuotas"
        origen_mov = "manual"

    elif tipo == "unico":
        descripcion_mov = observaciones or "Pago único"
        origen_mov = "manual"

    else:  # cheque
        descripcion_mov = observaciones or f"Cheque N° {numero_cheque} ({banco})"
        origen_mov = "cheque"

    MovimientoCuenta.objects.create(
        cuenta=cuenta,
        tipo="pago",
        monto=monto,
        descripcion=descripcion_mov,
        origen=origen_mov
    )

    # ===============================
    # IMPUTAR PAGO A CUOTAS
    # ===============================
    if tipo == "cuota":
        if not plan:
            messages.error(request, "La cuenta no tiene plan de pago.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

        monto_restante = monto
        cuota_id = request.POST.get("cuota_id")

        if not cuota_id:
            messages.error(request, "Seleccioná la cuota a imputar.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

        if not plan.cuotas.filter(id=cuota_id).exists():
            messages.error(request, "La cuota seleccionada no pertenece al plan.")
            return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

        cuota_inicio = plan.cuotas.get(id=cuota_id)
        cuotas_plan = plan.cuotas.filter(numero__gte=cuota_inicio.numero)

        for cuota in cuotas_plan:
            if monto_restante <= 0:
                break

            saldo = cuota.saldo_pendiente or Decimal("0")
            aplicar = min(monto_restante, saldo)

            if aplicar <= 0:
                continue

            PagoCuota.objects.create(
                pago=pago,
                cuota=cuota,
                monto_aplicado=aplicar
            )

            try:
                cuota.marcar_pagada()
            except Exception:
                pass

            monto_restante -= aplicar

        try:
            plan.verificar_finalizacion()
        except Exception:
            pass

    # ===============================
    # Recalcular saldo y guardar saldo posterior
    # ===============================
    try:
        cuenta.recalcular_saldo()
    except Exception:
        pass

    pago.saldo_posterior = cuenta.saldo
    pago.save(update_fields=["saldo_posterior"])

    return redirect("cuentas:recibo_pago_pdf", pago_id=pago.id)


# ==========================================================
# REGISTRAR PAGO GESTORÍA
# ==========================================================
@login_required
@transaction.atomic
def registrar_pago_gestoria(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    if not cuenta.venta or not cuenta.venta.gestoria:
        messages.error(request, "No hay gestoría asociada a esta cuenta.")
        return redirect(
            "cuentas:cuenta_corriente_detalle",
            cuenta_id=cuenta.id
        )

    if request.method == "POST":
        try:
            monto = _parse_monto_argentino(request.POST.get("monto"))
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect(
                "cuentas:cuenta_corriente_detalle",
                cuenta_id=cuenta.id
            )

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a 0.")
            return redirect(
                "cuentas:cuenta_corriente_detalle",
                cuenta_id=cuenta.id
            )

        pago = Pago.objects.create(
            cuenta=cuenta,
            forma_pago="efectivo",
            monto_total=monto,
            observaciones="Pago gestoría"
        )

        # 👇 ESTE ES EL FIX CLAVE (DEBE RESTAR)
        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            tipo="pago",
            monto=monto,
            descripcion="Pago de gestoría",
            origen="manual"   # ← NO "gestoria"
        )

        try:
            cuenta.recalcular_saldo()
        except Exception:
            pass

        return redirect(
            "cuentas:recibo_pago_pdf",
            pago_id=pago.id
        )

    return render(
        request,
        "cuentas/registrar_pago_gestoria.html",
        {"cuenta": cuenta}
    )


# ==========================================================
# RECIBO DE PAGO PDF
# ==========================================================
@login_required
def recibo_pago_pdf(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta
    cliente = cuenta.cliente

    fecha_str = timezone.now().strftime("%d/%m/%Y %H:%M")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="recibo_{pago.id}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ==================================================
    # COLORES CORPORATIVOS
    # ==================================================
    AZUL = colors.HexColor("#002855")
    NARANJA = colors.HexColor("#FF6C1A")
    GRIS = colors.HexColor("#666666")

    # ==================================================
    # ENCABEZADO
    # ==================================================
    header = Table(
        [[
            Paragraph(
                "<b>AMICHETTI AUTOMOTORES</b><br/>"
                "Titular: Amichetti Hugo Alberto<br/>"
                "CUIT: 20-13814200-1 – Tel: 2474660154",
                styles["Normal"]
            ),
            Paragraph(
                f"<b>RECIBO N° {pago.id:08d}</b><br/>{fecha_str}",
                styles["Normal"]
            )
        ]],
        colWidths=[11 * cm, 5 * cm]
    )

    header.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header)
    elements.append(Spacer(1, 20))

    # ==================================================
    # TÍTULO
    # ==================================================
    titulo_table = Table(
        [[
            Paragraph("<b>Comprobante de pago</b>", styles["Heading2"]),
            Paragraph(f"Fecha y hora: {fecha_str}", styles["Normal"])
        ]],
        colWidths=[10 * cm, 6 * cm],
        style=[
            ("LINEBELOW", (0, 0), (-1, 0), 1, NARANJA),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ]
    )

    elements.append(titulo_table)
    elements.append(Spacer(1, 18))

    # ==================================================
    # DATOS DEL CLIENTE
    # ==================================================
    documento = (
        getattr(cliente, "cuit", None)
        or getattr(cliente, "dni", None)
        or "-"
    )

    elements.append(Paragraph("<b>Datos del cliente</b>", styles["Heading3"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Nombre: {cliente.nombre_completo}", styles["Normal"]))
    elements.append(Paragraph(f"CUIT/DNI: {documento}", styles["Normal"]))
    elements.append(Spacer(1, 16))

    # ==================================================
    # DETALLE DEL PAGO
    # ==================================================
    elements.append(Paragraph("<b>Detalle del pago</b>", styles["Heading3"]))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(
        f"Método de pago: {pago.get_forma_pago_display()}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Monto abonado: $ {pago.monto_total:,.2f}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Observación: {pago.observaciones or '-'}",
        styles["Normal"]
    ))

    elements.append(Spacer(1, 12))

    # ==================================================
    # CONCEPTO DEL PAGO (CUOTA / ÚNICO / CHEQUE)
    # ==================================================
    ultimo_mov = (
        cuenta.movimientos
        .filter(tipo="pago")
        .order_by("-fecha")
        .first()
    )

    if ultimo_mov:
        elements.append(Paragraph(
            f"Concepto del pago: {ultimo_mov.descripcion}",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 12))

    # ==================================================
    # SALDO REAL PENDIENTE (PLAN / CUOTAS)
    # ==================================================
    plan = getattr(cuenta, "plan_pago", None)
    saldo_plan = Decimal("0")

    if plan:
        saldo_plan = sum(
            (cuota.saldo_pendiente for cuota in plan.cuotas.all()),
            Decimal("0")
        )

    elements.append(
        Paragraph(
            f"<b>Saldo pendiente del plan de pago:</b> "
            f"<font color='red'><b>$ {saldo_plan:,.2f}</b></font>",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 50))

    # ==================================================
    # FIRMA
    # ==================================================
    elements.append(
        Paragraph(
            "<para alignment='right'>"
            "<font color='#666666'>"
            "_____________________________<br/>"
            "Firma y aclaración"
            "</font></para>",
            styles["Normal"]
        )
    )

    doc.build(elements)
    return response


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
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id)

    ficha = vehiculo.ficha
    ficha.imputar_gastos_permuta_en_cuenta(cuenta)

    messages.success(request, "Vehículo vinculado correctamente.")

    return redirect(
        "cuentas:cuenta_corriente_detalle",
        cuenta_id=cuenta.id
    )


# ==========================================================
# ELIMINAR PLAN DE PAGO
# ==========================================================
@login_required
@transaction.atomic
def eliminar_plan_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    if hasattr(cuenta, "plan_pago"):
        cuenta.plan_pago.delete()
        cuenta.recalcular_saldo()
    return redirect(
        "cuentas:cuenta_corriente_detalle",
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
    return redirect(
        "cuentas:cuenta_corriente_detalle",
        cuenta_id=cuenta_id
    )


# ==========================================================
# HISTORIAL DE FINANCIACIÓN
# ==========================================================
@login_required
def historial_financiacion(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)
    plan = getattr(cuenta, "plan_pago", None)
    cuotas = plan.cuotas.all() if plan else []

    return render(
        request,
        "cuentas/historial_financiacion.html",
        {
            "cuenta": cuenta,
            "plan": plan,
            "cuotas": cuotas,
        }
    )
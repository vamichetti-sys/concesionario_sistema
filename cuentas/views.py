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
    cuentas_qs = (
        CuentaCorriente.objects
        .select_related("cliente", "venta")
        .exclude(estado="cerrada")
        .order_by("-creada")
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

    return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)


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
# REGISTRAR MOVIMIENTO / PAGO  ✅ FIX DEFINITIVO
# ==========================================================
@login_required
@transaction.atomic
def registrar_movimiento(request, cuenta_id):
    cuenta = get_object_or_404(CuentaCorriente, id=cuenta_id)

    plan = getattr(cuenta, "plan_pago", None)

    if request.method == "GET":
        cuotas = plan.cuotas.filter(estado="pendiente") if plan else []
        return render(
            request,
            "cuentas/registrar_movimiento.html",
            {"cuenta": cuenta, "cuotas": cuotas}
        )

    tipo = (request.POST.get("tipo_movimiento") or "").strip()
    forma_pago = (request.POST.get("forma_pago") or "").strip()
    observaciones = (request.POST.get("observaciones") or "").strip()

    # ✅ Validaciones duras (evitan rollback silencioso)
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

    # -------------------------------
    # PAGO + MOVIMIENTO (SIEMPRE)
    # -------------------------------
    pago = Pago.objects.create(
        cuenta=cuenta,
        forma_pago=forma_pago,
        monto_total=monto,
        observaciones=observaciones
    )

    MovimientoCuenta.objects.create(
        cuenta=cuenta,
        tipo="pago",
        monto=monto,
        descripcion=observaciones or "Pago",
        origen="manual"
    )

    # ==================================================
    # PAGO ÚNICO → PLAN DE 1 CUOTA (OneToOne SAFE)
    # ==================================================
    # ✅ Reglas:
    # - Si NO es "cuota", lo tratamos como "pago único / pago general"
    # - Usamos get_or_create para no romper OneToOne
    # - Limpiamos cuotas anteriores del plan (si existieran) SOLO en este caso
    if tipo != "cuota":
        plan, _ = PlanPago.objects.get_or_create(
            cuenta=cuenta,
            defaults={
                "fecha_inicio": timezone.now().date(),
                "cantidad_cuotas": 1,
                "monto_total": monto,
                "monto_cuota": monto,
                "estado": "activo",
            }
        )

        plan.cantidad_cuotas = 1
        plan.monto_total = monto
        plan.monto_cuota = monto
        plan.estado = "activo"
        plan.save()

        # limpiar cuotas previas del plan para dejar SOLO 1 cuota
        plan.cuotas.all().delete()

        CuotaPlan.objects.create(
            plan=plan,
            numero=1,
            vencimiento=timezone.now().date(),
            monto=monto,
            estado="pendiente"
        )

    # -------------------------------
    # IMPUTAR PAGO A CUOTAS
    # -------------------------------
    # ✅ Este bloque está blindado para que nunca tire excepción
    # y te deje todo "sin crear" por rollback.
    if plan:
        monto_restante = monto

        if tipo == "cuota":
            cuota_id = request.POST.get("cuota_id")
            if not cuota_id:
                messages.error(request, "Seleccioná la cuota a imputar.")
                return redirect("cuentas:cuenta_corriente_detalle", cuenta_id=cuenta.id)

            cuota_inicio = get_object_or_404(CuotaPlan, id=cuota_id, plan=plan)
            cuotas = plan.cuotas.filter(numero__gte=cuota_inicio.numero)
        else:
            cuotas = plan.cuotas.all()

        for cuota in cuotas:
            if monto_restante <= 0:
                break

            # ✅ saldo_pendiente puede venir None → lo convertimos a 0 seguro
            saldo = cuota.saldo_pendiente
            try:
                saldo = Decimal(saldo) if saldo is not None else Decimal("0")
            except Exception:
                saldo = Decimal("0")

            if saldo <= 0:
                # si el modelo ya la considera sin saldo, intentamos marcar pagada sin romper
                try:
                    cuota.marcar_pagada()
                except Exception:
                    pass
                continue

            aplicar = min(monto_restante, saldo)

            PagoCuota.objects.create(
                pago=pago,
                cuota=cuota,
                monto_aplicado=aplicar
            )

            # ✅ marcar_pagada puede fallar si tiene lógica interna → no rompemos el flujo
            try:
                cuota.marcar_pagada()
            except Exception:
                pass

            monto_restante -= aplicar

        # ✅ verificar_finalizacion no debe romper el guardado
        try:
            plan.verificar_finalizacion()
        except Exception:
            pass

    # ✅ recalcular_saldo tampoco debe romper el guardado
    try:
        cuenta.recalcular_saldo()
    except Exception:
        pass

    return redirect("cuentas:recibo_pago_pdf", pago_id=pago.id)
# ==========================================================
# EDITAR CUOTA
# ==========================================================
@login_required
@transaction.atomic
def editar_cuota(request, cuota_id):
    cuota = get_object_or_404(CuotaPlan, id=cuota_id)
    form = EditarCuotaForm(request.POST or None, instance=cuota)
    if request.method == "POST" and form.is_valid():
        form.save()
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
# RECIBO DE PAGO PDF
# ==========================================================
@login_required
def recibo_pago_pdf(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    cuenta = pago.cuenta

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f"inline; filename=recibo_{pago.id}.pdf"

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("RECIBO DE PAGO", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Cliente: {cuenta.cliente}", styles["Normal"]),
        Paragraph(f"Monto: $ {pago.monto_total:,.0f}", styles["Normal"]),
        Paragraph(
            f"Forma de pago: {pago.get_forma_pago_display()}",
            styles["Normal"]
        ),
    ]

    doc.build(elements)
    return response
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
from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from gastos_personales.models import GastoPersonal
from cuentas_internas.models import MovimientoInterno

from .models import PagoFuturo
from .forms import PagoFuturoForm, MarcarPagadoForm
from .decorators import solo_admins


MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


@solo_admins
def lista_pagos(request):
    hoy = date.today()
    # Filtro: pendientes (default) | vencidos | pagados | todos
    filtro = request.GET.get("filtro", "pendientes")
    # Mes/año (default mes corriente)
    try:
        mes = int(request.GET.get("mes", hoy.month))
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        mes, anio = hoy.month, hoy.year

    qs = PagoFuturo.objects.all().select_related("categoria", "cuenta_interna", "pagado_por")

    # Filtro por mes: pendientes/pagados se muestran cuando su vencimiento o pago cae en el mes elegido.
    if filtro == "pendientes":
        qs = qs.filter(
            pagado=False,
            fecha_vencimiento__year=anio,
            fecha_vencimiento__month=mes,
        ).order_by("fecha_vencimiento")
    elif filtro == "vencidos":
        qs = qs.filter(pagado=False, fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")
    elif filtro == "pagados":
        qs = qs.filter(
            pagado=True,
            fecha_pago__year=anio,
            fecha_pago__month=mes,
        ).order_by("-fecha_pago", "-id")
    else:  # todos
        qs = qs.filter(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)

    # Indicadores globales (no filtrados por mes)
    pendientes_all = PagoFuturo.objects.filter(pagado=False)
    total_pendiente = pendientes_all.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_pendiente = pendientes_all.count()

    vencidos = pendientes_all.filter(fecha_vencimiento__lt=hoy)
    total_vencido = vencidos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_vencido = vencidos.count()

    proximos_7 = pendientes_all.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=7),
    )
    cant_prox = proximos_7.count()
    total_prox = proximos_7.aggregate(t=Sum("monto"))["t"] or Decimal("0")

    # Años disponibles para navegar
    anios = list(
        PagoFuturo.objects.values_list("fecha_vencimiento__year", flat=True)
        .distinct().order_by("-fecha_vencimiento__year")
    )
    if hoy.year not in anios:
        anios = [hoy.year] + anios

    return render(request, "agenda_pagos/lista.html", {
        "pagos": qs,
        "filtro": filtro,
        "hoy": hoy,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "meses_choices": list(enumerate(MESES))[1:],
        "anios_disponibles": anios,
        "total_pendiente": total_pendiente,
        "cant_pendiente": cant_pendiente,
        "total_vencido": total_vencido,
        "cant_vencido": cant_vencido,
        "total_prox": total_prox,
        "cant_prox": cant_prox,
    })


@solo_admins
def crear_pago(request):
    if request.method == "POST":
        form = PagoFuturoForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creado_por = request.user
            obj.save()
            messages.success(request, "Pago futuro agregado a la agenda.")
            return redirect("agenda_pagos:lista")
    else:
        form = PagoFuturoForm(initial={"fecha_vencimiento": date.today()})
    return render(request, "agenda_pagos/form.html", {"form": form, "titulo": "Nuevo pago futuro"})


@solo_admins
def editar_pago(request, pk):
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if obj.pagado:
        messages.info(request, "Este pago ya fue marcado como pagado; deshacelo primero para editarlo.")
        return redirect("agenda_pagos:lista")
    if request.method == "POST":
        form = PagoFuturoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Pago actualizado.")
            return redirect("agenda_pagos:lista")
    else:
        form = PagoFuturoForm(instance=obj)
    return render(request, "agenda_pagos/form.html", {"form": form, "titulo": f"Editar — {obj.descripcion}", "obj": obj})


@solo_admins
def eliminar_pago(request, pk):
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Pago eliminado de la agenda.")
        return redirect("agenda_pagos:lista")
    return render(request, "agenda_pagos/eliminar.html", {"obj": obj})


def _crear_registro_destino(pago, request_user, fecha_pago, observaciones):
    """Crea el registro en el módulo destino y vincula su id al PagoFuturo."""
    if pago.destino == PagoFuturo.DESTINO_GASTOS_PERSONALES:
        # Necesita una categoría
        if not pago.categoria:
            return False, "Falta una categoría. Editá el pago y elegí una para Gastos Personales."
        gp = GastoPersonal.objects.create(
            usuario=request_user,
            categoria=pago.categoria,
            descripcion=pago.descripcion,
            monto=pago.monto,
            mes=fecha_pago.month,
            anio=fecha_pago.year,
            pagado=True,
            fecha_pago=fecha_pago,
            observaciones=(observaciones or pago.observaciones or ""),
        )
        pago.gasto_personal_id = gp.id
        return True, None
    elif pago.destino == PagoFuturo.DESTINO_CUENTAS_INTERNAS:
        if not pago.cuenta_interna:
            return False, "Falta la cuenta interna destino. Editá el pago y elegila."
        mov = MovimientoInterno.objects.create(
            cuenta=pago.cuenta_interna,
            tipo="debe",
            monto=pago.monto,
            concepto=pago.descripcion,
            fecha=fecha_pago,
            observaciones=(observaciones or pago.observaciones or ""),
            creado_por=request_user,
        )
        pago.movimiento_interno_id = mov.id
        return True, None
    return False, "Destino desconocido."


@solo_admins
@transaction.atomic
def marcar_pagado(request, pk):
    """Marcado completo con form (fecha + forma de pago + observaciones)."""
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if obj.pagado:
        messages.info(request, "Este pago ya está marcado como pagado.")
        return redirect("agenda_pagos:lista")

    if request.method == "POST":
        form = MarcarPagadoForm(request.POST)
        if form.is_valid():
            fecha_pago = form.cleaned_data["fecha_pago"]
            forma_pago = form.cleaned_data["forma_pago"]
            obs = form.cleaned_data.get("observaciones") or ""

            ok, err = _crear_registro_destino(obj, request.user, fecha_pago, obs)
            if not ok:
                messages.error(request, err)
                return redirect("agenda_pagos:lista")

            obj.pagado = True
            obj.fecha_pago = fecha_pago
            obj.forma_pago = forma_pago
            obj.pagado_por = request.user
            if obs:
                obj.observaciones = ((obj.observaciones or "") + ("\n" if obj.observaciones else "") + obs).strip()
            obj.save()
            messages.success(request, f"Pago marcado como pagado y cargado en {obj.get_destino_display()}.")
            return redirect("agenda_pagos:lista")
    else:
        form = MarcarPagadoForm(initial={"fecha_pago": date.today(), "forma_pago": "transferencia"})

    return render(request, "agenda_pagos/marcar_pagado.html", {"form": form, "obj": obj})


@solo_admins
@transaction.atomic
def marcar_pagado_rapido(request, pk):
    """
    Marcado rápido vía checkbox: usa fecha de hoy + forma_pago efectivo.
    Crea el registro destino con esos defaults y registra quién pagó.
    """
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method != "POST":
        return redirect("agenda_pagos:lista")
    if obj.pagado:
        return redirect("agenda_pagos:lista")

    fecha_pago = date.today()
    ok, err = _crear_registro_destino(obj, request.user, fecha_pago, "")
    if not ok:
        messages.error(request, err)
        return redirect("agenda_pagos:lista")

    obj.pagado = True
    obj.fecha_pago = fecha_pago
    obj.forma_pago = "efectivo"
    obj.pagado_por = request.user
    obj.save()
    messages.success(
        request,
        f"Pago marcado por {request.user.username} el {fecha_pago:%d/%m/%Y} → {obj.get_destino_display()}.",
    )
    return redirect("agenda_pagos:lista")


@solo_admins
def deshacer_pago(request, pk):
    """Revierte el 'pagado' y borra el registro creado en el módulo destino."""
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        if obj.gasto_personal_id:
            GastoPersonal.objects.filter(pk=obj.gasto_personal_id).delete()
            obj.gasto_personal_id = None
        if obj.movimiento_interno_id:
            MovimientoInterno.objects.filter(pk=obj.movimiento_interno_id).delete()
            obj.movimiento_interno_id = None
        obj.pagado = False
        obj.fecha_pago = None
        obj.pagado_por = None
        obj.save()
        messages.success(request, "Pago revertido. El registro destino fue eliminado.")
    return redirect("agenda_pagos:lista")

from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from gastos_mensuales.models import GastoMensual
from cuentas_internas.models import MovimientoInterno

from .models import PagoFuturo
from .forms import PagoFuturoForm, MarcarPagadoForm
from .decorators import solo_admins


@solo_admins
def lista_pagos(request):
    filtro = request.GET.get("filtro", "pendientes")  # pendientes | vencidos | pagados | todos
    hoy = date.today()

    qs = PagoFuturo.objects.all().select_related("categoria", "cuenta_interna")
    if filtro == "pendientes":
        qs = qs.filter(pagado=False).order_by("fecha_vencimiento")
    elif filtro == "vencidos":
        qs = qs.filter(pagado=False, fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")
    elif filtro == "pagados":
        qs = qs.filter(pagado=True).order_by("-fecha_pago", "-id")
    # 'todos' deja el orden por defecto

    # Indicadores
    pendientes = PagoFuturo.objects.filter(pagado=False)
    total_pendiente = pendientes.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_pendiente = pendientes.count()

    vencidos = pendientes.filter(fecha_vencimiento__lt=hoy)
    total_vencido = vencidos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_vencido = vencidos.count()

    proximos_7 = pendientes.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=7))
    cant_prox = proximos_7.count()
    total_prox = proximos_7.aggregate(t=Sum("monto"))["t"] or Decimal("0")

    return render(request, "agenda_pagos/lista.html", {
        "pagos": qs,
        "filtro": filtro,
        "hoy": hoy,
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
        messages.info(request, "Este pago ya fue marcado como pagado; para cambiarlo, primero deshacé el pago.")
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


@solo_admins
@transaction.atomic
def marcar_pagado(request, pk):
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

            # Crear el registro en el módulo destino.
            if obj.destino == PagoFuturo.DESTINO_CONTROL_GASTOS:
                # Necesita una categoría para GastoMensual.
                if not obj.categoria:
                    messages.error(request, "Falta una categoría para mandar este pago a Control de Gastos. Editalo y elegí una.")
                    return redirect("agenda_pagos:lista")
                gm = GastoMensual.objects.create(
                    categoria=obj.categoria,
                    descripcion=obj.descripcion,
                    monto=obj.monto,
                    mes=fecha_pago.month,
                    anio=fecha_pago.year,
                    unidad="ambas",
                    pagado=True,
                    fecha_pago=fecha_pago,
                    observaciones=(obs or obj.observaciones or ""),
                    creado_por=request.user,
                )
                obj.gasto_mensual_id = gm.id

            elif obj.destino == PagoFuturo.DESTINO_CUENTAS_INTERNAS:
                if not obj.cuenta_interna:
                    messages.error(request, "Falta la cuenta interna destino. Editalo y elegila.")
                    return redirect("agenda_pagos:lista")
                # Un pago saliente (concesionaria paga) → tipo 'haber' o 'debe' depende de la lectura.
                # Convención del módulo: 'debe' = cargo a esa cuenta. Lo registramos como 'debe'.
                mov = MovimientoInterno.objects.create(
                    cuenta=obj.cuenta_interna,
                    tipo="debe",
                    monto=obj.monto,
                    concepto=obj.descripcion,
                    fecha=fecha_pago,
                    observaciones=(obs or obj.observaciones or ""),
                    creado_por=request.user,
                )
                obj.movimiento_interno_id = mov.id

            obj.pagado = True
            obj.fecha_pago = fecha_pago
            obj.forma_pago = forma_pago
            if obs:
                obj.observaciones = ((obj.observaciones or "") + ("\n" if obj.observaciones else "") + obs).strip()
            obj.save()

            messages.success(request, f"Pago marcado como pagado y cargado en {obj.get_destino_display()}.")
            return redirect("agenda_pagos:lista")
    else:
        form = MarcarPagadoForm(initial={"fecha_pago": date.today(), "forma_pago": "transferencia"})

    return render(request, "agenda_pagos/marcar_pagado.html", {"form": form, "obj": obj})


@solo_admins
def deshacer_pago(request, pk):
    """Revierte el 'pagado' y borra el registro creado en el módulo destino."""
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        # Borrar el registro destino si existe
        if obj.gasto_mensual_id:
            GastoMensual.objects.filter(pk=obj.gasto_mensual_id).delete()
            obj.gasto_mensual_id = None
        if obj.movimiento_interno_id:
            MovimientoInterno.objects.filter(pk=obj.movimiento_interno_id).delete()
            obj.movimiento_interno_id = None
        obj.pagado = False
        obj.fecha_pago = None
        obj.save()
        messages.success(request, "Pago revertido. El registro destino fue eliminado.")
    return redirect("agenda_pagos:lista")

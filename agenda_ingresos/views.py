from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from .models import IngresoFuturo
from .forms import IngresoFuturoForm, MarcarCobradoForm
from .decorators import solo_admins

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ==========================================================
# HELPERS
# ==========================================================
def _sync_destino_ingreso(ingreso, default_user):
    """Crea/actualiza el registro de ingreso en el módulo destino."""
    from gastos_mensuales.models import IngresoMensual
    from gastos_personales.models import IngresoPersonal

    fecha_ref = ingreso.fecha_cobro or ingreso.fecha_vencimiento
    mes, anio = fecha_ref.month, fecha_ref.year
    concepto = ingreso.concepto or ingreso.descripcion

    if ingreso.destino == IngresoFuturo.DESTINO_CONTROL_INGRESOS:
        if ingreso.ingreso_mensual_id and IngresoMensual.objects.filter(pk=ingreso.ingreso_mensual_id).exists():
            IngresoMensual.objects.filter(pk=ingreso.ingreso_mensual_id).update(
                concepto=concepto, descripcion=ingreso.descripcion,
                monto=ingreso.monto, mes=mes, anio=anio, fecha=fecha_ref,
            )
        else:
            im = IngresoMensual.objects.create(
                concepto=concepto, descripcion=ingreso.descripcion,
                monto=ingreso.monto, mes=mes, anio=anio, fecha=fecha_ref,
                creado_por=ingreso.creado_por or default_user,
            )
            ingreso.ingreso_mensual_id = im.id
            ingreso.save(update_fields=["ingreso_mensual_id"])
    else:
        user_destino = ingreso.cobrado_por or ingreso.creado_por or default_user
        if ingreso.ingreso_personal_id and IngresoPersonal.objects.filter(pk=ingreso.ingreso_personal_id).exists():
            IngresoPersonal.objects.filter(pk=ingreso.ingreso_personal_id).update(
                usuario=user_destino, concepto=concepto, descripcion=ingreso.descripcion,
                monto=ingreso.monto, mes=mes, anio=anio, fecha=fecha_ref,
            )
        else:
            ip = IngresoPersonal.objects.create(
                usuario=user_destino, concepto=concepto, descripcion=ingreso.descripcion,
                monto=ingreso.monto, mes=mes, anio=anio, fecha=fecha_ref,
            )
            ingreso.ingreso_personal_id = ip.id
            ingreso.save(update_fields=["ingreso_personal_id"])


def _borrar_destino_ingreso(ingreso):
    from gastos_mensuales.models import IngresoMensual
    from gastos_personales.models import IngresoPersonal
    if ingreso.ingreso_mensual_id:
        IngresoMensual.objects.filter(pk=ingreso.ingreso_mensual_id).delete()
        ingreso.ingreso_mensual_id = None
    if ingreso.ingreso_personal_id:
        IngresoPersonal.objects.filter(pk=ingreso.ingreso_personal_id).delete()
        ingreso.ingreso_personal_id = None
    ingreso.save(update_fields=["ingreso_mensual_id", "ingreso_personal_id"])


def _crear_proximo_mes(ingreso, user):
    next_fecha = ingreso.proxima_fecha_mensual
    if next_fecha < date.today():
        return None
    if ingreso.recurrente_hasta and next_fecha > ingreso.recurrente_hasta:
        return None
    if IngresoFuturo.objects.filter(
        descripcion=ingreso.descripcion, destino=ingreso.destino,
        fecha_vencimiento=next_fecha,
    ).exists():
        return None
    return IngresoFuturo.objects.create(
        descripcion=ingreso.descripcion, concepto=ingreso.concepto,
        monto=0, fecha_vencimiento=next_fecha, destino=ingreso.destino,
        es_recurrente_mensual=ingreso.es_recurrente_mensual,
        recurrente_hasta=ingreso.recurrente_hasta,
        observaciones=ingreso.observaciones, creado_por=user,
    )


# ==========================================================
# VISTAS
# ==========================================================
@solo_admins
def lista_ingresos(request):
    hoy = date.today()
    filtro = request.GET.get("filtro", "pendientes")
    try:
        mes = int(request.GET.get("mes", hoy.month))
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        mes, anio = hoy.month, hoy.year

    qs = IngresoFuturo.objects.all().select_related("cobrado_por")
    if filtro == "pendientes":
        qs = qs.filter(cobrado=False, fecha_vencimiento__year=anio, fecha_vencimiento__month=mes).order_by("fecha_vencimiento")
    elif filtro == "vencidos":
        qs = qs.filter(cobrado=False, fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")
    elif filtro == "cobrados":
        qs = qs.filter(cobrado=True, fecha_cobro__year=anio, fecha_cobro__month=mes).order_by("-fecha_cobro", "-id")
    else:
        qs = qs.filter(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)

    destino_sel = request.GET.get("destino") or ""
    if destino_sel:
        qs = qs.filter(destino=destino_sel)

    pendientes_all = IngresoFuturo.objects.filter(cobrado=False)
    total_pendiente = pendientes_all.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_pendiente = pendientes_all.count()
    vencidos = pendientes_all.filter(fecha_vencimiento__lt=hoy)
    total_vencido = vencidos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_vencido = vencidos.count()
    proximos_7 = pendientes_all.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=7))
    cant_prox = proximos_7.count()
    total_prox = proximos_7.aggregate(t=Sum("monto"))["t"] or Decimal("0")

    anios = list(
        IngresoFuturo.objects.values_list("fecha_vencimiento__year", flat=True)
        .distinct().order_by("-fecha_vencimiento__year")
    )
    if hoy.year not in anios:
        anios = [hoy.year] + anios

    return render(request, "agenda_ingresos/lista.html", {
        "ingresos": qs,
        "filtro": filtro,
        "hoy": hoy,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "meses_choices": list(enumerate(MESES))[1:],
        "anios_disponibles": anios,
        "destino_choices": IngresoFuturo.DESTINO_CHOICES,
        "destino_sel": destino_sel,
        "total_pendiente": total_pendiente,
        "cant_pendiente": cant_pendiente,
        "total_vencido": total_vencido,
        "cant_vencido": cant_vencido,
        "total_prox": total_prox,
        "cant_prox": cant_prox,
    })


@solo_admins
@transaction.atomic
def crear_ingreso(request):
    if request.method == "POST":
        form = IngresoFuturoForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creado_por = request.user
            if obj.monto is None:
                obj.monto = 0
            obj.save()
            messages.success(request, "Ingreso agendado.")
            return redirect("agenda_ingresos:lista")
    else:
        form = IngresoFuturoForm(initial={"fecha_vencimiento": date.today()})
    return render(request, "agenda_ingresos/form.html", {"form": form, "titulo": "Nuevo ingreso futuro"})


@solo_admins
@transaction.atomic
def editar_ingreso(request, pk):
    obj = get_object_or_404(IngresoFuturo, pk=pk)
    if request.method == "POST":
        form = IngresoFuturoForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.monto is None:
                obj.monto = 0
            obj.save()
            if obj.cobrado:
                _sync_destino_ingreso(obj, request.user)
            messages.success(request, "Ingreso actualizado.")
            return redirect("agenda_ingresos:lista")
    else:
        form = IngresoFuturoForm(instance=obj)
    return render(request, "agenda_ingresos/form.html", {"form": form, "titulo": f"Editar — {obj.descripcion}", "obj": obj})


@solo_admins
@transaction.atomic
def eliminar_ingreso(request, pk):
    obj = get_object_or_404(IngresoFuturo, pk=pk)
    if request.method == "POST":
        _borrar_destino_ingreso(obj)
        obj.delete()
        messages.success(request, "Ingreso eliminado de la agenda y del módulo destino.")
        return redirect("agenda_ingresos:lista")
    return render(request, "agenda_ingresos/eliminar.html", {"obj": obj})


@solo_admins
@transaction.atomic
def marcar_cobrado(request, pk):
    obj = get_object_or_404(IngresoFuturo, pk=pk)
    if obj.cobrado:
        messages.info(request, "Este ingreso ya está marcado como cobrado.")
        return redirect("agenda_ingresos:lista")

    if request.method == "POST":
        form = MarcarCobradoForm(request.POST)
        if form.is_valid():
            obj.monto = form.cleaned_data["monto"]
            obj.cobrado = True
            obj.fecha_cobro = form.cleaned_data["fecha_cobro"]
            obj.forma_cobro = form.cleaned_data["forma_cobro"]
            obj.cobrado_por = request.user
            obs = form.cleaned_data.get("observaciones") or ""
            if obs:
                obj.observaciones = ((obj.observaciones or "") + ("\n" if obj.observaciones else "") + obs).strip()
            obj.save()

            _sync_destino_ingreso(obj, request.user)

            extra = ""
            if form.cleaned_data.get("agregar_mes_siguiente"):
                nuevo = _crear_proximo_mes(obj, request.user)
                if nuevo:
                    extra = f" Se agendó el del mes siguiente ({nuevo.fecha_vencimiento:%d/%m/%Y})."
            messages.success(request, f"Ingreso de ${obj.monto:.0f} cargado en {obj.get_destino_display()}.{extra}")
            return redirect("agenda_ingresos:lista")
    else:
        form = MarcarCobradoForm(initial={
            "monto": obj.monto if obj.monto else None,
            "fecha_cobro": date.today(),
            "forma_cobro": "transferencia",
            "agregar_mes_siguiente": obj.es_recurrente_mensual,
        })
    return render(request, "agenda_ingresos/marcar_cobrado.html", {"form": form, "obj": obj})


@solo_admins
@transaction.atomic
def deshacer_cobro(request, pk):
    obj = get_object_or_404(IngresoFuturo, pk=pk)
    if request.method == "POST":
        _borrar_destino_ingreso(obj)
        obj.cobrado = False
        obj.fecha_cobro = None
        obj.cobrado_por = None
        obj.save()
        messages.success(request, "Ingreso revertido a pendiente.")
    return redirect("agenda_ingresos:lista")

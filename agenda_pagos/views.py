import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse

from gastos_mensuales.models import GastoMensual, CategoriaGasto
from gastos_personales.models import GastoPersonal

from .models import PagoFuturo
from .forms import PagoFuturoForm, MarcarPagadoForm
from .decorators import solo_admins


MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ==========================================================
# HELPERS
# ==========================================================

def _sync_destino(pago, default_user):
    """
    Asegura que exista el registro en el módulo destino y refleje el
    estado actual del PagoFuturo. Si no existe, lo crea (incluso si el
    pago todavía no está marcado pagado — para que aparezca como
    pendiente en su módulo desde que se agenda). Si ya existe, lo
    actualiza con los campos actuales del PagoFuturo.

    Devuelve (ok, error_message).
    """
    if not pago.categoria:
        return False, "Falta una categoría. Editá el pago y elegí una."

    # Mes/año del registro destino: usamos la fecha de pago si existe,
    # si no la fecha de vencimiento (para que aparezca en el mes correcto
    # antes de pagarse).
    fecha_ref = pago.fecha_pago or pago.fecha_vencimiento
    mes = fecha_ref.month
    anio = fecha_ref.year

    if pago.destino == PagoFuturo.DESTINO_CONTROL_GASTOS:
        if pago.gasto_mensual_id and GastoMensual.objects.filter(pk=pago.gasto_mensual_id).exists():
            GastoMensual.objects.filter(pk=pago.gasto_mensual_id).update(
                categoria=pago.categoria,
                descripcion=pago.descripcion,
                monto=pago.monto,
                mes=mes, anio=anio,
                pagado=pago.pagado,
                fecha_pago=pago.fecha_pago,
                observaciones=pago.observaciones or "",
            )
        else:
            gm = GastoMensual.objects.create(
                categoria=pago.categoria,
                descripcion=pago.descripcion,
                monto=pago.monto,
                mes=mes, anio=anio,
                unidad="ambas",
                pagado=pago.pagado,
                fecha_pago=pago.fecha_pago,
                observaciones=pago.observaciones or "",
                creado_por=pago.creado_por or default_user,
            )
            pago.gasto_mensual_id = gm.id
            pago.save(update_fields=["gasto_mensual_id"])
        return True, None

    if pago.destino == PagoFuturo.DESTINO_GASTOS_PERSONALES:
        # Para Gastos Personales necesitamos un usuario. Mientras no esté
        # pagado, lo asignamos al usuario que creó el pago (admin).
        # Al pagarlo, lo reasignamos a pagado_por.
        user_destino = pago.pagado_por or pago.creado_por or default_user
        if pago.gasto_personal_id and GastoPersonal.objects.filter(pk=pago.gasto_personal_id).exists():
            GastoPersonal.objects.filter(pk=pago.gasto_personal_id).update(
                usuario=user_destino,
                categoria=pago.categoria,
                descripcion=pago.descripcion,
                monto=pago.monto,
                mes=mes, anio=anio,
                pagado=pago.pagado,
                fecha_pago=pago.fecha_pago,
                observaciones=pago.observaciones or "",
            )
        else:
            gp = GastoPersonal.objects.create(
                usuario=user_destino,
                categoria=pago.categoria,
                descripcion=pago.descripcion,
                monto=pago.monto,
                mes=mes, anio=anio,
                pagado=pago.pagado,
                fecha_pago=pago.fecha_pago,
                observaciones=pago.observaciones or "",
            )
            pago.gasto_personal_id = gp.id
            pago.save(update_fields=["gasto_personal_id"])
        return True, None

    return False, "Destino desconocido."


def _borrar_destino(pago):
    """Borra el registro destino asociado al PagoFuturo (si existe)."""
    if pago.gasto_mensual_id:
        GastoMensual.objects.filter(pk=pago.gasto_mensual_id).delete()
        pago.gasto_mensual_id = None
    if pago.gasto_personal_id:
        GastoPersonal.objects.filter(pk=pago.gasto_personal_id).delete()
        pago.gasto_personal_id = None
    pago.save(update_fields=["gasto_mensual_id", "gasto_personal_id"])


def _crear_proximo_mes(pago, request_user):
    """
    Crea el pago del mes siguiente (misma descripción, +1 mes) si todavía
    no existe uno con la misma descripción/destino/fecha. Devuelve el
    nuevo PagoFuturo o None si no se creó.
    """
    next_fecha = pago.proxima_fecha_mensual
    # No generar meses que ya quedaron vencidos (evita encadenar placeholders
    # en $0 cuando se paga un mes atrasado). Solo se agenda a futuro.
    if next_fecha < date.today():
        return None
    # Respeta la fecha de término del recurrente (ej: último mes de un crédito).
    if pago.recurrente_hasta and next_fecha > pago.recurrente_hasta:
        return None
    if PagoFuturo.objects.filter(
        descripcion=pago.descripcion,
        destino=pago.destino,
        fecha_vencimiento=next_fecha,
    ).exists():
        return None
    nuevo = PagoFuturo.objects.create(
        descripcion=pago.descripcion,
        monto=0,  # se completa cuando se pague
        fecha_vencimiento=next_fecha,
        categoria=pago.categoria,
        destino=pago.destino,
        es_recurrente_mensual=pago.es_recurrente_mensual,
        recurrente_hasta=pago.recurrente_hasta,
        observaciones=pago.observaciones,
        creado_por=request_user,
    )
    _sync_destino(nuevo, request_user)
    return nuevo


def _next_month_date(fecha):
    """Misma fecha pero en el mes siguiente (clamp al último día)."""
    year = fecha.year + (1 if fecha.month == 12 else 0)
    month = 1 if fecha.month == 12 else fecha.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(fecha.day, last_day))


# ==========================================================
# VISTAS
# ==========================================================

@solo_admins
def lista_pagos(request):
    hoy = date.today()
    filtro = request.GET.get("filtro", "pendientes")
    try:
        mes = int(request.GET.get("mes", hoy.month))
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        mes, anio = hoy.month, hoy.year

    qs = PagoFuturo.objects.all().select_related("categoria", "pagado_por")

    if filtro == "pendientes":
        qs = qs.filter(pagado=False, fecha_vencimiento__year=anio, fecha_vencimiento__month=mes).order_by("fecha_vencimiento")
    elif filtro == "vencidos":
        qs = qs.filter(pagado=False, fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")
    elif filtro == "pagados":
        qs = qs.filter(pagado=True, fecha_pago__year=anio, fecha_pago__month=mes).order_by("-fecha_pago", "-id")
    else:
        qs = qs.filter(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)

    # Filtro opcional por categoría
    categoria_sel = request.GET.get("categoria") or ""
    if categoria_sel:
        qs = qs.filter(categoria_id=categoria_sel)

    # Filtro por destino (Control de Gastos / Gastos Personales)
    destino_sel = request.GET.get("destino") or ""
    if destino_sel:
        qs = qs.filter(destino=destino_sel)

    # Filtro por tipo de gasto (fijo/mensual vs variable)
    tipo_sel = request.GET.get("tipo") or ""
    if tipo_sel == "fijo":
        qs = qs.filter(categoria__es_fijo=True)
    elif tipo_sel == "variable":
        qs = qs.filter(categoria__es_fijo=False)

    pendientes_all = PagoFuturo.objects.filter(pagado=False)
    total_pendiente = pendientes_all.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_pendiente = pendientes_all.count()
    vencidos = pendientes_all.filter(fecha_vencimiento__lt=hoy)
    total_vencido = vencidos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    cant_vencido = vencidos.count()
    proximos_7 = pendientes_all.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=7))
    cant_prox = proximos_7.count()
    total_prox = proximos_7.aggregate(t=Sum("monto"))["t"] or Decimal("0")

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
        "categorias": CategoriaGasto.objects.filter(activa=True).order_by("nombre"),
        "categoria_sel": categoria_sel,
        "destino_choices": PagoFuturo.DESTINO_CHOICES,
        "destino_sel": destino_sel,
        "tipo_sel": tipo_sel,
        "total_pendiente": total_pendiente,
        "cant_pendiente": cant_pendiente,
        "total_vencido": total_vencido,
        "cant_vencido": cant_vencido,
        "total_prox": total_prox,
        "cant_prox": cant_prox,
    })


@solo_admins
@transaction.atomic
def crear_pago(request):
    if request.method == "POST":
        form = PagoFuturoForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creado_por = request.user
            if obj.monto is None:
                obj.monto = 0
            obj.save()
            ok, err = _sync_destino(obj, request.user)
            if not ok:
                messages.warning(request, f"Pago agendado pero no se pudo crear el registro en el módulo destino: {err}")
            else:
                messages.success(request, f"Pago agendado y cargado en {obj.get_destino_display()} como pendiente.")
            return redirect("agenda_pagos:lista")
    else:
        form = PagoFuturoForm(initial={"fecha_vencimiento": date.today()})
    return render(request, "agenda_pagos/form.html", {"form": form, "titulo": "Nuevo pago futuro"})


@solo_admins
@transaction.atomic
def editar_pago(request, pk):
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        form = PagoFuturoForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.monto is None:
                obj.monto = 0
            obj.save()
            _sync_destino(obj, request.user)
            messages.success(request, "Pago actualizado.")
            return redirect("agenda_pagos:lista")
    else:
        form = PagoFuturoForm(instance=obj)
    return render(request, "agenda_pagos/form.html", {"form": form, "titulo": f"Editar — {obj.descripcion}", "obj": obj})


@solo_admins
@transaction.atomic
def eliminar_pago(request, pk):
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        _borrar_destino(obj)
        obj.delete()
        messages.success(request, "Pago eliminado de la agenda y del módulo destino.")
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
            monto = form.cleaned_data["monto"]
            fecha_pago = form.cleaned_data["fecha_pago"]
            forma_pago = form.cleaned_data["forma_pago"]
            obs = form.cleaned_data.get("observaciones") or ""
            agregar_mes_sig = form.cleaned_data.get("agregar_mes_siguiente", False)

            obj.monto = monto  # el monto real se carga acá
            obj.pagado = True
            obj.fecha_pago = fecha_pago
            obj.forma_pago = forma_pago
            obj.pagado_por = request.user
            if obs:
                obj.observaciones = ((obj.observaciones or "") + ("\n" if obj.observaciones else "") + obs).strip()
            obj.save()

            ok, err = _sync_destino(obj, request.user)
            if not ok:
                messages.error(request, err)
                return redirect("agenda_pagos:lista")

            extra = ""
            if agregar_mes_sig:
                nuevo = _crear_proximo_mes(obj, request.user)
                if nuevo:
                    extra = f" Se agendó el del mes siguiente ({nuevo.fecha_vencimiento:%d/%m/%Y})."
                else:
                    extra = " (El del mes siguiente ya existía, no se duplicó.)"
            messages.success(request, f"Pago de ${monto:.0f} cargado en {obj.get_destino_display()}.{extra}")
            return redirect("agenda_pagos:lista")
    else:
        form = MarcarPagadoForm(initial={
            "monto": obj.monto if obj.monto else None,
            "fecha_pago": date.today(),
            "forma_pago": "transferencia",
            "agregar_mes_siguiente": obj.es_recurrente_mensual,
        })

    return render(request, "agenda_pagos/marcar_pagado.html", {"form": form, "obj": obj})


# (marcar_pagado_rapido fue removido: ahora todo pago pasa por
#  marcar_pagado que pide monto + pregunta si agendar el mes siguiente.)


@solo_admins
@transaction.atomic
def deshacer_pago(request, pk):
    obj = get_object_or_404(PagoFuturo, pk=pk)
    if request.method == "POST":
        obj.pagado = False
        obj.fecha_pago = None
        obj.pagado_por = None
        obj.save()
        _sync_destino(obj, request.user)  # actualiza el registro a pendiente
        messages.success(request, "Pago revertido a pendiente.")
    return redirect("agenda_pagos:lista")


@solo_admins
def copiar_mes_anterior(request):
    """
    GET: muestra los pagos del mes anterior con checkboxes para elegir
         cuáles copiar. Los recurrentes vienen pre-tildados.
    POST: copia solo los pagos cuyos PKs fueron tildados.
    """
    hoy = date.today()
    # Tomar destino del query (o del POST si está)
    try:
        mes = int(request.GET.get("mes", request.POST.get("mes_destino", hoy.month)))
        anio = int(request.GET.get("anio", request.POST.get("anio_destino", hoy.year)))
    except ValueError:
        mes, anio = hoy.month, hoy.year
    if not (1 <= mes <= 12 and anio > 0):
        mes, anio = hoy.month, hoy.year

    mes_origen = 12 if mes == 1 else mes - 1
    anio_origen = anio - 1 if mes == 1 else anio

    pagos_origen = PagoFuturo.objects.filter(
        fecha_vencimiento__year=anio_origen,
        fecha_vencimiento__month=mes_origen,
    ).select_related("categoria").order_by("fecha_vencimiento")

    # Cuáles ya existen en el mes destino (para mostrar y excluir)
    last_day = calendar.monthrange(anio, mes)[1]
    pagos_info = []
    for p in pagos_origen:
        nueva_fecha = date(anio, mes, min(p.fecha_vencimiento.day, last_day))
        ya_existe = PagoFuturo.objects.filter(
            descripcion=p.descripcion,
            destino=p.destino,
            fecha_vencimiento=nueva_fecha,
        ).exists()
        pagos_info.append({"pago": p, "nueva_fecha": nueva_fecha, "ya_existe": ya_existe})

    if request.method == "POST":
        seleccionados = set(request.POST.getlist("pagos_seleccionados"))
        creados = 0
        with transaction.atomic():
            for info in pagos_info:
                p = info["pago"]
                if str(p.pk) not in seleccionados:
                    continue
                if info["ya_existe"]:
                    continue
                nuevo = PagoFuturo.objects.create(
                    descripcion=p.descripcion,
                    monto=p.monto,
                    fecha_vencimiento=info["nueva_fecha"],
                    categoria=p.categoria,
                    destino=p.destino,
                    es_recurrente_mensual=p.es_recurrente_mensual,
                    recurrente_hasta=p.recurrente_hasta,
                    observaciones=p.observaciones,
                    creado_por=request.user,
                )
                _sync_destino(nuevo, request.user)
                creados += 1
        if creados > 0:
            messages.success(request, f"Se copiaron {creados} pago{'s' if creados != 1 else ''} al {MESES[mes]} {anio}.")
        else:
            messages.info(request, "No se copió ningún pago.")
        return redirect(f"{reverse('agenda_pagos:lista')}?mes={mes}&anio={anio}")

    return render(request, "agenda_pagos/copiar_mes_anterior.html", {
        "pagos_info": pagos_info,
        "mes_destino": mes,
        "anio_destino": anio,
        "mes_origen": mes_origen,
        "anio_origen": anio_origen,
        "mes_destino_nombre": MESES[mes],
        "mes_origen_nombre": MESES[mes_origen],
    })


# ==========================================================
# PDF: AGENDA DE PAGOS (respeta los filtros de la lista)
# ==========================================================
@solo_admins
def pdf_agenda(request):
    from reportes.pdf_utils import render_pdf_listado

    hoy = date.today()
    filtro = request.GET.get("filtro", "pendientes")
    try:
        mes = int(request.GET.get("mes", hoy.month))
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        mes, anio = hoy.month, hoy.year

    qs = PagoFuturo.objects.all().select_related("categoria", "pagado_por")
    if filtro == "pendientes":
        qs = qs.filter(pagado=False, fecha_vencimiento__year=anio, fecha_vencimiento__month=mes).order_by("fecha_vencimiento")
    elif filtro == "vencidos":
        qs = qs.filter(pagado=False, fecha_vencimiento__lt=hoy).order_by("fecha_vencimiento")
    elif filtro == "pagados":
        qs = qs.filter(pagado=True, fecha_pago__year=anio, fecha_pago__month=mes).order_by("-fecha_pago", "-id")
    else:
        qs = qs.filter(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)

    if request.GET.get("categoria"):
        qs = qs.filter(categoria_id=request.GET["categoria"])
    if request.GET.get("destino"):
        qs = qs.filter(destino=request.GET["destino"])
    tipo_sel = request.GET.get("tipo") or ""
    if tipo_sel == "fijo":
        qs = qs.filter(categoria__es_fijo=True)
    elif tipo_sel == "variable":
        qs = qs.filter(categoria__es_fijo=False)

    total = Decimal("0")
    filas = []
    for p in qs:
        total += p.monto or Decimal("0")
        filas.append([
            p.descripcion,
            p.categoria.nombre if p.categoria_id else "—",
            p.get_destino_display(),
            p.fecha_vencimiento.strftime("%d/%m/%Y") if p.fecha_vencimiento else "—",
            f"$ {(p.monto or 0):,.0f}".replace(",", "."),
            "Pagado" if p.pagado else ("Vencido" if p.vencido else "Pendiente"),
        ])

    etiquetas = {
        "pendientes": f"Pendientes – {MESES[mes]} {anio}",
        "vencidos": "Vencidos (todos)",
        "pagados": f"Pagados – {MESES[mes]} {anio}",
        "todos": f"Todos – {MESES[mes]} {anio}",
    }
    totales = ["", "", "", "TOTAL", f"$ {total:,.0f}".replace(",", "."), ""]

    return render_pdf_listado(
        filename=f"agenda_pagos_{filtro}.pdf",
        titulo="Agenda de Pagos",
        subtitulo=f"{etiquetas.get(filtro, '')} – {len(filas)} pago(s)",
        columnas=["Descripción", "Categoría", "Destino", "Vencimiento", "Monto", "Estado"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )

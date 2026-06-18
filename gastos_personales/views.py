from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.urls import reverse
from decimal import Decimal, InvalidOperation

from gastos_mensuales.models import CategoriaGasto
from .models import GastoPersonal, IngresoPersonal
from .forms import GastoPersonalForm, IngresoPersonalForm
from .decorators import solo_gestion_personal

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


@solo_gestion_personal
def resumen_mensual(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    # Solo los gastos del usuario logueado
    gastos = GastoPersonal.objects.filter(
        usuario=request.user, mes=mes, anio=anio,
    ).select_related("categoria").order_by("categoria__nombre")

    total_fijos = gastos.filter(categoria__es_fijo=True).aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_variables = gastos.filter(categoria__es_fijo=False).aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_general = total_fijos + total_variables
    total_pagado = gastos.filter(pagado=True).aggregate(t=Sum("monto"))["t"] or Decimal("0")
    total_pendiente = total_general - total_pagado

    por_categoria = (
        gastos.values("categoria__nombre", "categoria__es_fijo")
        .annotate(total=Sum("monto"))
        .order_by("-total")
    )

    anios_disponibles = list(
        GastoPersonal.objects.filter(usuario=request.user)
        .values_list("anio", flat=True).distinct().order_by("-anio")
    )
    if hoy.year not in anios_disponibles:
        anios_disponibles = [hoy.year] + anios_disponibles

    mes_anterior = mes - 1 if mes > 1 else 12
    anio_anterior = anio if mes > 1 else anio - 1
    total_mes_anterior = GastoPersonal.objects.filter(
        usuario=request.user, mes=mes_anterior, anio=anio_anterior,
    ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    variacion = None
    if total_mes_anterior > 0:
        variacion = ((total_general - total_mes_anterior) / total_mes_anterior * 100)

    return render(request, "gastos_personales/resumen.html", {
        "gastos": gastos,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "total_fijos": total_fijos,
        "total_variables": total_variables,
        "total_general": total_general,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "por_categoria": por_categoria,
        "anios_disponibles": anios_disponibles,
        "meses_choices": list(enumerate(MESES))[1:],
        "variacion": variacion,
        "mes_anterior_nombre": MESES[mes_anterior] if 1 <= mes_anterior <= 12 else "",
    })


@solo_gestion_personal
def agregar_gasto(request):
    hoy = date.today()
    if request.method == "POST":
        form = GastoPersonalForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.usuario = request.user
            gasto.save()
            messages.success(request, f"Gasto \"{gasto.categoria.nombre}\" registrado.")
            return redirect(f"{reverse('gastos_personales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")
    else:
        form = GastoPersonalForm(initial={"mes": hoy.month, "anio": hoy.year})
    return render(request, "gastos_personales/form.html", {"form": form, "titulo": "Registrar gasto personal"})


@solo_gestion_personal
def editar_gasto(request, pk):
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = GastoPersonalForm(request.POST, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto actualizado.")
            return redirect(f"{reverse('gastos_personales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")
    else:
        form = GastoPersonalForm(instance=gasto)
    return render(request, "gastos_personales/form.html", {
        "form": form, "titulo": f"Editar gasto – {gasto.categoria.nombre}", "gasto": gasto,
    })


@solo_gestion_personal
def eliminar_gasto(request, pk):
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    # Si este gasto se generó desde la Agenda de Pagos, borrarlo acá deja el
    # pago de la agenda apuntando a un id inexistente y el próximo sync lo
    # vuelve a crear (registro "zombie"). En ese caso hay que borrarlo desde
    # la agenda, donde se elimina el pago y su reflejo personal a la vez.
    from agenda_pagos.models import PagoFuturo
    origen_agenda = PagoFuturo.objects.filter(gasto_personal_id=gasto.pk).first()
    if origen_agenda is not None:
        if request.method == "POST":
            messages.warning(
                request,
                "Este gasto se generó desde la Agenda de Pagos. Para que no "
                "vuelva a aparecer, eliminá el pago desde la Agenda de Pagos."
            )
            return redirect(f"{reverse('gastos_personales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")
        return render(request, "gastos_personales/eliminar.html",
                      {"gasto": gasto, "origen_agenda": origen_agenda})
    if request.method == "POST":
        mes, anio = gasto.mes, gasto.anio
        gasto.delete()
        messages.success(request, "Gasto eliminado.")
        return redirect(f"{reverse('gastos_personales:resumen')}?mes={mes}&anio={anio}")
    return render(request, "gastos_personales/eliminar.html", {"gasto": gasto})


@solo_gestion_personal
def marcar_pagado(request, pk):
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        gasto.pagado = not gasto.pagado
        gasto.fecha_pago = date.today() if gasto.pagado else None
        gasto.save(update_fields=["pagado", "fecha_pago"])
        estado = "pagado" if gasto.pagado else "pendiente"
        messages.success(request, f"Gasto marcado como {estado}.")
    return redirect(f"{reverse('gastos_personales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")


@solo_gestion_personal
def actualizar_monto(request, pk):
    """Edición inline del monto desde la tabla de resumen."""
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        raw = (request.POST.get("monto") or "").strip().replace(",", ".")
        try:
            monto = Decimal(raw)
            if monto < 0:
                raise InvalidOperation
            gasto.monto = monto
            gasto.save(update_fields=["monto"])
            messages.success(request, "Monto actualizado.")
        except (InvalidOperation, ValueError):
            messages.error(request, "Monto inválido.")
    return redirect(f"{reverse('gastos_personales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")


@solo_gestion_personal
def duplicar_fijos(request):
    if request.method == "POST":
        mes = int(request.POST.get("mes_destino", 0))
        anio = int(request.POST.get("anio_destino", 0))
        if not (1 <= mes <= 12 and anio > 0):
            messages.error(request, "Mes o año inválido.")
            return redirect("gastos_personales:resumen")

        mes_origen = mes - 1 if mes > 1 else 12
        anio_origen = anio if mes > 1 else anio - 1

        fijos_origen = GastoPersonal.objects.filter(
            usuario=request.user, mes=mes_origen, anio=anio_origen, categoria__es_fijo=True,
        )
        if not fijos_origen.exists():
            messages.warning(request, f"No hay gastos fijos en {MESES[mes_origen]} {anio_origen}.")
            return redirect(f"{reverse('gastos_personales:resumen')}?mes={mes}&anio={anio}")

        if GastoPersonal.objects.filter(usuario=request.user, mes=mes, anio=anio, categoria__es_fijo=True).exists():
            messages.info(request, "Ya existen gastos fijos para este mes.")
            return redirect(f"{reverse('gastos_personales:resumen')}?mes={mes}&anio={anio}")

        for g in fijos_origen:
            GastoPersonal.objects.create(
                usuario=request.user, categoria=g.categoria, descripcion=g.descripcion,
                monto=g.monto, mes=mes, anio=anio,
            )
        messages.success(request, "Gastos fijos copiados del mes anterior.")
    return redirect(f"{reverse('gastos_personales:resumen')}?mes={mes}&anio={anio}")


# ==========================================================
# INGRESOS PERSONALES (privados por usuario, separados de los gastos)
# ==========================================================
@solo_gestion_personal
def ingresos_resumen(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    ingresos = IngresoPersonal.objects.filter(
        usuario=request.user, mes=mes, anio=anio,
    ).order_by("concepto")
    total_general = ingresos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    por_concepto = ingresos.values("concepto").annotate(total=Sum("monto")).order_by("-total")

    anios_disponibles = list(
        IngresoPersonal.objects.filter(usuario=request.user)
        .values_list("anio", flat=True).distinct().order_by("-anio")
    )
    if hoy.year not in anios_disponibles:
        anios_disponibles = [hoy.year] + anios_disponibles

    # Lo que está a ingresar: alquileres pendientes de cobro del mes
    from cuentas_internas.models import Alquiler
    a_ingresar = []
    total_a_ingresar = Decimal("0")
    for alq in Alquiler.objects.filter(activo=True):
        if alq.pagos.filter(periodo_mes=mes, periodo_anio=anio).exists():
            continue
        for f in alq.cronograma():
            if f["mes"] == mes and f["anio"] == anio:
                a_ingresar.append({"alquiler": alq, "monto": f["monto"]})
                total_a_ingresar += f["monto"] or Decimal("0")
                break

    return render(request, "gastos_personales/ingresos_resumen.html", {
        "ingresos": ingresos,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "total_general": total_general,
        "por_concepto": por_concepto,
        "anios_disponibles": anios_disponibles,
        "meses_choices": list(enumerate(MESES))[1:],
        "a_ingresar": a_ingresar,
        "total_a_ingresar": total_a_ingresar,
    })


@solo_gestion_personal
def agregar_ingreso(request):
    hoy = date.today()
    if request.method == "POST":
        form = IngresoPersonalForm(request.POST)
        if form.is_valid():
            ing = form.save(commit=False)
            ing.usuario = request.user
            ing.save()
            messages.success(request, f'Ingreso "{ing.concepto}" registrado.')
            return redirect(f"{reverse('gastos_personales:ingresos')}?mes={ing.mes}&anio={ing.anio}")
    else:
        form = IngresoPersonalForm(initial={"mes": hoy.month, "anio": hoy.year})
    return render(request, "gastos_personales/ingreso_form.html", {
        "form": form, "titulo": "Registrar ingreso personal",
    })


@solo_gestion_personal
def editar_ingreso(request, pk):
    ing = get_object_or_404(IngresoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = IngresoPersonalForm(request.POST, instance=ing)
        if form.is_valid():
            form.save()
            messages.success(request, "Ingreso actualizado.")
            return redirect(f"{reverse('gastos_personales:ingresos')}?mes={ing.mes}&anio={ing.anio}")
    else:
        form = IngresoPersonalForm(instance=ing)
    return render(request, "gastos_personales/ingreso_form.html", {
        "form": form, "titulo": f"Editar ingreso – {ing.concepto}", "ingreso": ing,
    })


@solo_gestion_personal
def eliminar_ingreso(request, pk):
    ing = get_object_or_404(IngresoPersonal, pk=pk, usuario=request.user)
    mes, anio = ing.mes, ing.anio
    if request.method == "POST":
        # Igual que con los gastos: si vino de la Agenda de Ingresos, borrarlo
        # acá lo resucitaría en el próximo sync. Hay que borrarlo desde la agenda.
        from agenda_ingresos.models import IngresoFuturo
        if IngresoFuturo.objects.filter(ingreso_personal_id=ing.pk).exists():
            messages.warning(
                request,
                "Este ingreso se generó desde la Agenda de Ingresos. Para que no "
                "vuelva a aparecer, eliminalo desde la Agenda de Ingresos."
            )
            return redirect(f"{reverse('gastos_personales:ingresos')}?mes={mes}&anio={anio}")
        ing.delete()
        messages.success(request, "Ingreso eliminado.")
    return redirect(f"{reverse('gastos_personales:ingresos')}?mes={mes}&anio={anio}")


@solo_gestion_personal
def actualizar_monto_ingreso(request, pk):
    ing = get_object_or_404(IngresoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        raw = (request.POST.get("monto") or "").strip().replace(",", ".")
        try:
            monto = Decimal(raw)
            if monto < 0:
                raise InvalidOperation
            ing.monto = monto
            ing.save(update_fields=["monto"])
            messages.success(request, "Monto actualizado.")
        except (InvalidOperation, ValueError):
            messages.error(request, "Monto inválido.")
    return redirect(f"{reverse('gastos_personales:ingresos')}?mes={ing.mes}&anio={ing.anio}")


@solo_gestion_personal
def pdf_ingresos(request):
    from reportes.pdf_utils import render_pdf_listado, MESES_ES
    hoy = date.today()
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    ingresos = IngresoPersonal.objects.filter(
        usuario=request.user, mes=mes, anio=anio,
    ).order_by("concepto")
    total = Decimal("0")
    filas = []
    for i in ingresos:
        total += i.monto or Decimal("0")
        filas.append([
            i.concepto,
            i.descripcion or "—",
            f"$ {(i.monto or 0):,.0f}".replace(",", "."),
        ])
    totales = ["", "TOTAL", f"$ {total:,.0f}".replace(",", ".")]
    return render_pdf_listado(
        filename=f"ingresos_personales_{mes:02d}_{anio}.pdf",
        titulo="Ingresos Personales",
        subtitulo=f"{MESES_ES[mes]} {anio} – {request.user.username} – {len(filas)} ingreso(s)",
        columnas=["Concepto", "Detalle", "Monto"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )


# ==========================================================
# PDF MENSUAL: gastos personales del usuario para mes/año
# ==========================================================
from django.contrib.auth.decorators import login_required as _login_required_pdf

@_login_required_pdf
def pdf_mensual(request):
    from datetime import date
    from decimal import Decimal
    from reportes.pdf_utils import render_pdf_listado, MESES_ES
    from .models import GastoPersonal

    hoy = date.today()
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    qs = (
        GastoPersonal.objects
        .filter(usuario=request.user, mes=mes, anio=anio)
        .select_related("categoria")
        .order_by("categoria__nombre", "descripcion")
    )

    total = Decimal("0")
    total_pagado = Decimal("0")
    filas = []
    for g in qs:
        total += g.monto or Decimal("0")
        if g.pagado:
            total_pagado += g.monto or Decimal("0")
        filas.append([
            g.categoria.nombre if g.categoria_id else "—",
            g.descripcion or "—",
            f"$ {(g.monto or 0):,.0f}".replace(",", "."),
            "Sí" if g.pagado else "No",
            g.fecha_pago.strftime("%d/%m/%Y") if g.fecha_pago else "—",
        ])

    totales = [
        "", "TOTAL",
        f"$ {total:,.0f}".replace(",", "."),
        f"Pagado: $ {total_pagado:,.0f}".replace(",", "."),
        "",
    ]

    return render_pdf_listado(
        filename=f"gastos_personales_{mes:02d}_{anio}.pdf",
        titulo="Gastos Personales",
        subtitulo=f"{MESES_ES[mes]} {anio} – {request.user.username} – {len(filas)} gasto(s)",
        columnas=["Categoría", "Descripción", "Monto", "Pagado", "Fecha pago"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )

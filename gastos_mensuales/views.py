from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import date

from .models import CategoriaGasto, GastoMensual, ResumenGastosMensual, IngresoMensual
from .forms import CategoriaGastoForm, GastoMensualForm, IngresoMensualForm


MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ==========================================================
# RESUMEN MENSUAL (PANTALLA PRINCIPAL)
# ==========================================================
@login_required
def resumen_mensual(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    gastos = GastoMensual.objects.filter(
        mes=mes, anio=anio,
    ).select_related("categoria").order_by("categoria__nombre")

    # Separar gastos de vehículos (sincronizados desde la ficha) del resto,
    # para mostrarlos en solapas distintas y que no se mezclen.
    gastos_vehiculos = [g for g in gastos if g.descripcion and "[GCF:" in g.descripcion]
    gastos_generales = [g for g in gastos if not (g.descripcion and "[GCF:" in g.descripcion)]
    total_vehiculos = sum((g.monto for g in gastos_vehiculos), Decimal("0"))

    # Totales
    total_fijos = gastos.filter(
        categoria__es_fijo=True
    ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    total_variables = gastos.filter(
        categoria__es_fijo=False
    ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    total_general = total_fijos + total_variables

    total_pagado = gastos.filter(
        pagado=True
    ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    total_pendiente = total_general - total_pagado

    # Por categoria
    por_categoria = (
        gastos.values("categoria__nombre", "categoria__es_fijo")
        .annotate(total=Sum("monto"))
        .order_by("-total")
    )

    # Meses disponibles para navegacion
    anios_disponibles = (
        GastoMensual.objects.values_list("anio", flat=True)
        .distinct()
        .order_by("-anio")
    )
    if hoy.year not in anios_disponibles:
        anios_disponibles = [hoy.year] + list(anios_disponibles)

    # Comparar con mes anterior
    mes_anterior = mes - 1 if mes > 1 else 12
    anio_anterior = anio if mes > 1 else anio - 1
    total_mes_anterior = GastoMensual.objects.filter(
        mes=mes_anterior, anio=anio_anterior,
    ).aggregate(t=Sum("monto"))["t"] or Decimal("0")

    variacion = None
    if total_mes_anterior > 0:
        variacion = ((total_general - total_mes_anterior) / total_mes_anterior * 100)

    return render(request, "gastos_mensuales/resumen.html", {
        "gastos": gastos,
        "gastos_generales": gastos_generales,
        "gastos_vehiculos": gastos_vehiculos,
        "total_vehiculos": total_vehiculos,
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
        "total_mes_anterior": total_mes_anterior,
        "mes_anterior_nombre": MESES[mes_anterior] if 1 <= mes_anterior <= 12 else "",
    })


# ==========================================================
# AGREGAR GASTO
# ==========================================================
@login_required
def agregar_gasto(request):
    hoy = date.today()

    if request.method == "POST":
        form = GastoMensualForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.creado_por = request.user
            gasto.save()
            messages.success(request, f"Gasto \"{gasto.categoria.nombre}\" registrado.")
            return redirect(
                f"/gastos-mensuales/?mes={gasto.mes}&anio={gasto.anio}"
            )
    else:
        form = GastoMensualForm(initial={
            "mes": hoy.month,
            "anio": hoy.year,
        })

    return render(request, "gastos_mensuales/form.html", {
        "form": form,
        "titulo": "Registrar Gasto",
    })


# ==========================================================
# EDITAR GASTO
# ==========================================================
@login_required
def editar_gasto(request, pk):
    gasto = get_object_or_404(GastoMensual, pk=pk)

    if request.method == "POST":
        form = GastoMensualForm(request.POST, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto actualizado.")
            return redirect(
                f"/gastos-mensuales/?mes={gasto.mes}&anio={gasto.anio}"
            )
    else:
        form = GastoMensualForm(instance=gasto)

    return render(request, "gastos_mensuales/form.html", {
        "form": form,
        "titulo": f"Editar Gasto – {gasto.categoria.nombre}",
        "gasto": gasto,
    })


# ==========================================================
# ELIMINAR GASTO
# ==========================================================
@login_required
def eliminar_gasto(request, pk):
    gasto = get_object_or_404(GastoMensual, pk=pk)
    mes, anio = gasto.mes, gasto.anio

    if request.method == "POST":
        gasto.delete()
        messages.success(request, "Gasto eliminado.")
        return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={mes}&anio={anio}")

    return render(request, "gastos_mensuales/eliminar.html", {"gasto": gasto})


# ==========================================================
# MARCAR COMO PAGADO (RAPIDO)
# ==========================================================
@login_required
def marcar_pagado(request, pk):
    gasto = get_object_or_404(GastoMensual, pk=pk)

    if request.method == "POST":
        gasto.pagado = not gasto.pagado
        gasto.fecha_pago = date.today() if gasto.pagado else None
        gasto.save(update_fields=["pagado", "fecha_pago"])
        estado = "pagado" if gasto.pagado else "pendiente"
        messages.success(request, f"Gasto marcado como {estado}.")

    return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")


# ==========================================================
# ACTUALIZAR MONTO (EDICIÓN INLINE DESDE LA TABLA)
# ==========================================================
@login_required
def actualizar_monto(request, pk):
    gasto = get_object_or_404(GastoMensual, pk=pk)
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
    return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={gasto.mes}&anio={gasto.anio}")


# ==========================================================
# PDF MENSUAL: control de gastos del mes/año
# ==========================================================
@login_required
def pdf_mensual(request):
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

    qs = (
        GastoMensual.objects.filter(mes=mes, anio=anio)
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
        try:
            unidad = g.get_unidad_display()
        except Exception:
            unidad = g.unidad or "—"
        filas.append([
            g.categoria.nombre if g.categoria_id else "—",
            g.descripcion or "—",
            unidad,
            f"$ {(g.monto or 0):,.0f}".replace(",", "."),
            "Sí" if g.pagado else "No",
        ])

    totales = ["", "", "TOTAL", f"$ {total:,.0f}".replace(",", "."),
               f"Pagado: $ {total_pagado:,.0f}".replace(",", ".")]

    return render_pdf_listado(
        filename=f"control_gastos_{mes:02d}_{anio}.pdf",
        titulo="Gastos Concesionario",
        subtitulo=f"{MESES_ES[mes]} {anio} – {len(filas)} gasto(s)",
        columnas=["Categoría", "Detalle", "Unidad", "Monto", "Pagado"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )


# ==========================================================
# CONTROL DE INGRESOS (separado de los gastos)
# ==========================================================
@login_required
def ingresos_resumen(request):
    hoy = date.today()
    mes = int(request.GET.get("mes", hoy.month))
    anio = int(request.GET.get("anio", hoy.year))

    ingresos = IngresoMensual.objects.filter(mes=mes, anio=anio).order_by("concepto")
    total_general = ingresos.aggregate(t=Sum("monto"))["t"] or Decimal("0")
    por_concepto = (
        ingresos.values("concepto").annotate(total=Sum("monto")).order_by("-total")
    )

    anios_disponibles = list(
        IngresoMensual.objects.values_list("anio", flat=True).distinct().order_by("-anio")
    )
    if hoy.year not in anios_disponibles:
        anios_disponibles = [hoy.year] + anios_disponibles

    # Ganancia de Control de Stock (ventas confirmadas del mes)
    from reportes.services import ganancia_ventas_mes
    ganancia_ventas, ganancia_detalle = ganancia_ventas_mes(mes, anio)

    return render(request, "gastos_mensuales/ingresos_resumen.html", {
        "ingresos": ingresos,
        "mes": mes,
        "anio": anio,
        "mes_nombre": MESES[mes] if 1 <= mes <= 12 else "",
        "total_general": total_general,
        "por_concepto": por_concepto,
        "anios_disponibles": anios_disponibles,
        "meses_choices": list(enumerate(MESES))[1:],
        "ganancia_ventas": ganancia_ventas,
        "ganancia_detalle": ganancia_detalle,
        "total_con_ganancia": (total_general or 0) + (ganancia_ventas or 0),
    })


@login_required
def agregar_ingreso(request):
    hoy = date.today()
    if request.method == "POST":
        form = IngresoMensualForm(request.POST)
        if form.is_valid():
            ing = form.save(commit=False)
            ing.creado_por = request.user
            ing.save()
            messages.success(request, f'Ingreso "{ing.concepto}" registrado.')
            return redirect(f"/gastos-mensuales/ingresos/?mes={ing.mes}&anio={ing.anio}")
    else:
        form = IngresoMensualForm(initial={"mes": hoy.month, "anio": hoy.year})
    return render(request, "gastos_mensuales/ingreso_form.html", {
        "form": form, "titulo": "Registrar Ingreso",
    })


@login_required
def editar_ingreso(request, pk):
    ing = get_object_or_404(IngresoMensual, pk=pk)
    if request.method == "POST":
        form = IngresoMensualForm(request.POST, instance=ing)
        if form.is_valid():
            form.save()
            messages.success(request, "Ingreso actualizado.")
            return redirect(f"/gastos-mensuales/ingresos/?mes={ing.mes}&anio={ing.anio}")
    else:
        form = IngresoMensualForm(instance=ing)
    return render(request, "gastos_mensuales/ingreso_form.html", {
        "form": form, "titulo": f"Editar Ingreso – {ing.concepto}", "ingreso": ing,
    })


@login_required
def eliminar_ingreso(request, pk):
    ing = get_object_or_404(IngresoMensual, pk=pk)
    mes, anio = ing.mes, ing.anio
    if request.method == "POST":
        ing.delete()
        messages.success(request, "Ingreso eliminado.")
    return redirect(f"/gastos-mensuales/ingresos/?mes={mes}&anio={anio}")


@login_required
def actualizar_monto_ingreso(request, pk):
    ing = get_object_or_404(IngresoMensual, pk=pk)
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
    return redirect(f"/gastos-mensuales/ingresos/?mes={ing.mes}&anio={ing.anio}")


@login_required
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

    ingresos = IngresoMensual.objects.filter(mes=mes, anio=anio).order_by("concepto")
    total = Decimal("0")
    filas = []
    for i in ingresos:
        total += i.monto or Decimal("0")
        try:
            unidad = i.get_unidad_display()
        except Exception:
            unidad = i.unidad or "—"
        filas.append([
            i.concepto,
            i.descripcion or "—",
            unidad,
            f"$ {(i.monto or 0):,.0f}".replace(",", "."),
        ])
    totales = ["", "TOTAL", "", f"$ {total:,.0f}".replace(",", ".")]
    return render_pdf_listado(
        filename=f"ingresos_{mes:02d}_{anio}.pdf",
        titulo="Control de Ingresos",
        subtitulo=f"{MESES_ES[mes]} {anio} – {len(filas)} ingreso(s)",
        columnas=["Concepto", "Detalle", "Unidad", "Monto"],
        filas=filas,
        totales=totales if filas else None,
        pie=f"Generado el {hoy.strftime('%d/%m/%Y')}",
    )


# ==========================================================
# CATEGORIAS
# ==========================================================
@login_required
def lista_categorias(request):
    categorias = CategoriaGasto.objects.all()
    return render(request, "gastos_mensuales/categorias.html", {
        "categorias": categorias,
    })


@login_required
def crear_categoria(request):
    if request.method == "POST":
        form = CategoriaGastoForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Categoria \"{cat.nombre}\" creada.")
            return redirect("gastos_mensuales:categorias")
    else:
        form = CategoriaGastoForm()

    return render(request, "gastos_mensuales/form_categoria.html", {
        "form": form,
        "titulo": "Nueva Categoria",
    })


@login_required
def editar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaGasto, pk=pk)

    if request.method == "POST":
        form = CategoriaGastoForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria actualizada.")
            return redirect("gastos_mensuales:categorias")
    else:
        form = CategoriaGastoForm(instance=categoria)

    return render(request, "gastos_mensuales/form_categoria.html", {
        "form": form,
        "titulo": f"Editar – {categoria.nombre}",
        "categoria": categoria,
    })


# ==========================================================
# DUPLICAR GASTOS FIJOS DEL MES ANTERIOR
# ==========================================================
@login_required
def duplicar_fijos(request):
    if request.method == "POST":
        mes = int(request.POST.get("mes_destino", 0))
        anio = int(request.POST.get("anio_destino", 0))

        if not (1 <= mes <= 12 and anio > 0):
            messages.error(request, "Mes o anio invalido.")
            return redirect("gastos_mensuales:resumen")

        # Mes origen
        mes_origen = mes - 1 if mes > 1 else 12
        anio_origen = anio if mes > 1 else anio - 1

        fijos_origen = GastoMensual.objects.filter(
            mes=mes_origen,
            anio=anio_origen,
            categoria__es_fijo=True,
        )

        if not fijos_origen.exists():
            messages.warning(request, f"No hay gastos fijos en {mes_origen}/{anio_origen}.")
            return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={mes}&anio={anio}")

        # Verificar que no existan ya
        existentes = GastoMensual.objects.filter(
            mes=mes, anio=anio, categoria__es_fijo=True,
        ).count()

        if existentes > 0:
            messages.info(request, "Ya existen gastos fijos para este mes.")
            return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={mes}&anio={anio}")

        creados = 0
        for gasto in fijos_origen:
            GastoMensual.objects.create(
                categoria=gasto.categoria,
                descripcion=gasto.descripcion,
                monto=gasto.monto,
                mes=mes,
                anio=anio,
                unidad=gasto.unidad,
                pagado=False,
                creado_por=request.user,
            )
            creados += 1

        messages.success(request, f"{creados} gasto(s) fijo(s) copiados a {MESES[mes]} {anio}.")
        return redirect(f"{reverse('gastos_mensuales:resumen')}?mes={mes}&anio={anio}")

    return redirect("gastos_mensuales:resumen")

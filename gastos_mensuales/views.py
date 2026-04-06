from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from datetime import date

from .models import CategoriaGasto, GastoMensual, ResumenGastosMensual
from .forms import CategoriaGastoForm, GastoMensualForm


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

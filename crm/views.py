from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from datetime import date

from .models import Prospecto, Seguimiento
from .forms import ProspectoForm, SeguimientoForm
from clientes.models import Cliente


# ==========================================================
# LISTA DE PROSPECTOS
# ==========================================================
@login_required
def lista_prospectos(request):
    query = request.GET.get("q", "")
    etapa_filtro = request.GET.get("etapa", "")
    origen_filtro = request.GET.get("origen", "")
    prioridad_filtro = request.GET.get("prioridad", "")

    prospectos = Prospecto.objects.all()

    if query:
        prospectos = prospectos.filter(
            Q(nombre_completo__icontains=query)
            | Q(telefono__icontains=query)
            | Q(email__icontains=query)
        )

    if etapa_filtro:
        prospectos = prospectos.filter(etapa=etapa_filtro)

    if origen_filtro:
        prospectos = prospectos.filter(origen=origen_filtro)

    if prioridad_filtro:
        prospectos = prospectos.filter(prioridad=prioridad_filtro)

    # Contadores por etapa
    contadores = dict(
        Prospecto.objects.values_list("etapa")
        .annotate(c=Count("id"))
        .values_list("etapa", "c")
    )

    # Prospectos con contacto pendiente para hoy o atrasado
    hoy = date.today()
    pendientes_hoy = Prospecto.objects.filter(
        fecha_proximo_contacto__lte=hoy,
        etapa__in=["nuevo", "contactado", "en_negociacion", "presupuestado"],
    ).count()

    return render(request, "crm/lista.html", {
        "prospectos": prospectos,
        "query": query,
        "etapa_filtro": etapa_filtro,
        "origen_filtro": origen_filtro,
        "prioridad_filtro": prioridad_filtro,
        "contadores": contadores,
        "pendientes_hoy": pendientes_hoy,
        "etapas": Prospecto.ETAPA_CHOICES,
        "origenes": Prospecto.ORIGEN_CHOICES,
        "prioridades": Prospecto.PRIORIDAD_CHOICES,
    })


# ==========================================================
# CREAR PROSPECTO
# ==========================================================
@login_required
def crear_prospecto(request):
    if request.method == "POST":
        form = ProspectoForm(request.POST)
        if form.is_valid():
            prospecto = form.save(commit=False)
            if not prospecto.asignado_a:
                prospecto.asignado_a = request.user
            prospecto.save()
            messages.success(request, f"Prospecto \"{prospecto.nombre_completo}\" creado.")
            return redirect("crm:detalle", pk=prospecto.pk)
    else:
        form = ProspectoForm()

    return render(request, "crm/form.html", {
        "form": form,
        "titulo": "Nuevo Prospecto",
    })


# ==========================================================
# DETALLE DE PROSPECTO
# ==========================================================
@login_required
def detalle_prospecto(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)
    seguimientos = prospecto.seguimientos.all()

    form_seguimiento = SeguimientoForm()

    return render(request, "crm/detalle.html", {
        "prospecto": prospecto,
        "seguimientos": seguimientos,
        "form_seguimiento": form_seguimiento,
    })


# ==========================================================
# EDITAR PROSPECTO
# ==========================================================
@login_required
def editar_prospecto(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)

    if request.method == "POST":
        form = ProspectoForm(request.POST, instance=prospecto)
        if form.is_valid():
            form.save()
            messages.success(request, "Prospecto actualizado.")
            return redirect("crm:detalle", pk=prospecto.pk)
    else:
        form = ProspectoForm(instance=prospecto)

    return render(request, "crm/form.html", {
        "form": form,
        "titulo": f"Editar – {prospecto.nombre_completo}",
        "prospecto": prospecto,
    })


# ==========================================================
# CAMBIAR ETAPA (RAPIDO)
# ==========================================================
@login_required
def cambiar_etapa(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)

    if request.method == "POST":
        nueva_etapa = request.POST.get("etapa")
        etapas_validas = [e[0] for e in Prospecto.ETAPA_CHOICES]

        if nueva_etapa in etapas_validas:
            prospecto.etapa = nueva_etapa
            prospecto.save(update_fields=["etapa", "fecha_actualizacion"])
            messages.success(
                request,
                f"Etapa actualizada a \"{prospecto.get_etapa_display()}\".",
            )

    return redirect("crm:detalle", pk=prospecto.pk)


# ==========================================================
# AGREGAR SEGUIMIENTO
# ==========================================================
@login_required
def agregar_seguimiento(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)

    if request.method == "POST":
        form = SeguimientoForm(request.POST)
        if form.is_valid():
            seguimiento = form.save(commit=False)
            seguimiento.prospecto = prospecto
            seguimiento.creado_por = request.user
            seguimiento.save()

            # Si estaba en "nuevo", avanza a "contactado"
            if prospecto.etapa == "nuevo":
                prospecto.etapa = "contactado"
                prospecto.save(update_fields=["etapa", "fecha_actualizacion"])

            messages.success(request, "Seguimiento registrado.")

    return redirect("crm:detalle", pk=prospecto.pk)


# ==========================================================
# CONVERTIR PROSPECTO A CLIENTE
# ==========================================================
@login_required
def convertir_a_cliente(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)

    if prospecto.cliente:
        messages.info(request, "Este prospecto ya fue convertido a cliente.")
        return redirect("crm:detalle", pk=prospecto.pk)

    if request.method == "POST":
        cliente = Cliente.objects.create(
            nombre_completo=prospecto.nombre_completo,
            telefono=prospecto.telefono,
            email=prospecto.email,
        )
        prospecto.cliente = cliente
        prospecto.etapa = "ganado"
        prospecto.save(update_fields=["cliente", "etapa", "fecha_actualizacion"])

        messages.success(
            request,
            f"Prospecto convertido a cliente \"{cliente.nombre_completo}\".",
        )
        return redirect("crm:detalle", pk=prospecto.pk)

    return render(request, "crm/convertir.html", {"prospecto": prospecto})


# ==========================================================
# ELIMINAR PROSPECTO
# ==========================================================
@login_required
def eliminar_prospecto(request, pk):
    prospecto = get_object_or_404(Prospecto, pk=pk)

    if request.method == "POST":
        nombre = prospecto.nombre_completo
        prospecto.delete()
        messages.success(request, f"Prospecto \"{nombre}\" eliminado.")
        return redirect("crm:lista")

    return render(request, "crm/eliminar.html", {"prospecto": prospecto})

from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q

from .models import Gestoria
from .forms import GestoriaForm


# ==========================================================
# PANTALLA PRINCIPAL GESTORÍA
# ==========================================================
def gestoria_inicio(request):
    return render(request, "gestoria/inicio.html")


# ==========================================================
# GESTORÍAS VIGENTES + BUSCADOR
# ==========================================================
def gestoria_vigentes(request):
    query = request.GET.get("q", "").strip()

    gestorias = (
        Gestoria.objects
        .filter(estado="vigente")
        .select_related("vehiculo", "cliente", "venta")
    )

    if query:
        gestorias = gestorias.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(venta__id__icontains=query)
        ).distinct()

    gestorias = gestorias.order_by("-fecha_creacion")

    return render(
        request,
        "gestoria/vigentes.html",
        {
            "gestorias": gestorias,
            "query": query,
        }
    )


# ==========================================================
# GESTORÍAS FINALIZADAS + BUSCADOR
# ==========================================================
def gestoria_finalizadas(request):
    query = request.GET.get("q", "").strip()

    gestorias = (
        Gestoria.objects
        .filter(
            estado="finalizada",
            fecha_finalizacion__isnull=False
        )
        .select_related("vehiculo", "cliente", "venta")
    )

    if query:
        gestorias = gestorias.filter(
            Q(cliente__nombre_completo__icontains=query) |
            Q(cliente__dni_cuit__icontains=query) |
            Q(vehiculo__marca__icontains=query) |
            Q(vehiculo__modelo__icontains=query) |
            Q(vehiculo__dominio__icontains=query) |
            Q(venta__id__icontains=query)
        ).distinct()

    gestorias = gestorias.order_by("-fecha_finalizacion")

    return render(
        request,
        "gestoria/finalizadas.html",
        {
            "gestorias": gestorias,
            "query": query,
        }
    )


# ==========================================================
# MARCAR GESTORÍA COMO FINALIZADA
# (SE MANTIENE PARA FLUJOS EXISTENTES)
# ==========================================================
def finalizar_gestoria(request, gestoria_id):
    gestoria = get_object_or_404(Gestoria, id=gestoria_id)

    if request.method == "POST":
        if gestoria.estado != "finalizada":
            gestoria.estado = "finalizada"
            gestoria.fecha_finalizacion = timezone.now()
            gestoria.save(update_fields=["estado", "fecha_finalizacion"])
            messages.success(request, "Gestoría finalizada correctamente")
        else:
            messages.info(request, "La gestoría ya estaba finalizada")
    else:
        messages.warning(request, "Acción inválida")

    return redirect("gestoria:vigentes")


# ==========================================================
# EDITAR / CREAR FICHA DE GESTORÍA
# ==========================================================
def editar_gestoria(request, gestoria_id):
    """
    Pantalla de ficha de gestoría.
    Permite editar documentación, estado y observaciones.
    NO finaliza automáticamente salvo que el estado cambie.
    """

    gestoria = get_object_or_404(Gestoria, id=gestoria_id)

    if request.method == "POST":
        form = GestoriaForm(request.POST, instance=gestoria)
        if form.is_valid():
            g = form.save(commit=False)

            # Finalización controlada desde la ficha
            if g.estado == "finalizada" and not g.fecha_finalizacion:
                g.fecha_finalizacion = timezone.now()

            if g.estado != gestoria.estado:
                messages.info(
                    request,
                    f"Estado de gestoría cambiado a {g.get_estado_display()}"
                )

            g.save()
            messages.success(request, "Gestoría actualizada correctamente")
            return redirect("gestoria:vigentes")
    else:
        form = GestoriaForm(instance=gestoria)

    return render(
        request,
        "gestoria/gestoria_form.html",
        {
            "gestoria": gestoria,
            "form": form
        }
    )


# ==========================================================
# HELPER: CREAR O VINCULAR GESTORÍA DESDE VENTA
# (SE MANTIENE, ALINEADO AL MODELO)
# ==========================================================
def crear_o_vincular_gestoria(venta, vehiculo, cliente):
    """
    Se utiliza desde Ventas cuando se asigna un cliente o se confirma una venta.
    Garantiza que la Gestoría exista y esté vinculada al cliente correcto.
    """

    # 🔒 Delegamos la lógica al modelo (fuente única de verdad)
    gestoria = Gestoria.crear_o_actualizar_desde_venta(
        venta=venta,
        vehiculo=vehiculo,
        cliente=cliente
    )

    return gestoria
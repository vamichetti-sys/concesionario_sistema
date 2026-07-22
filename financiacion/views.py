from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FinancieraForm
from .models import Financiera


@login_required
def index(request):
    """Panel de Financiación: financieras con las que se trabaja y las
    ventas financiadas (para asignarles la financiera que asumió la deuda)."""
    from ventas.models import Venta

    financieras = (
        Financiera.objects.all()
        .annotate(
            n_ventas=Count("ventas"),
            total_deuda=Sum("ventas__precio_venta"),
        )
    )

    ventas_financiadas = (
        Venta.objects.filter(financiado=True)
        .select_related("vehiculo", "cliente", "financiera")
        .order_by("financiera__nombre", "-id")
    )

    return render(request, "financiacion/index.html", {
        "page_title": "Financiación",
        "financieras": financieras,
        "ventas_financiadas": ventas_financiadas,
        "financieras_activas": Financiera.objects.filter(activa=True),
    })


@login_required
def crear_financiera(request):
    if request.method == "POST":
        form = FinancieraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Financiera creada correctamente.")
            return redirect("financiacion:index")
    else:
        form = FinancieraForm()
    return render(request, "financiacion/form.html", {"form": form})


@login_required
def editar_financiera(request, pk):
    financiera = get_object_or_404(Financiera, pk=pk)
    if request.method == "POST":
        form = FinancieraForm(request.POST, instance=financiera)
        if form.is_valid():
            form.save()
            messages.success(request, "Financiera actualizada correctamente.")
            return redirect("financiacion:index")
    else:
        form = FinancieraForm(instance=financiera)
    return render(request, "financiacion/form.html", {
        "form": form,
        "editando": True,
        "financiera": financiera,
    })


@login_required
def eliminar_financiera(request, pk):
    financiera = get_object_or_404(Financiera, pk=pk)
    if request.method == "POST":
        financiera.delete()
        messages.success(request, "Financiera eliminada.")
        return redirect("financiacion:index")
    return render(request, "financiacion/eliminar.html", {
        "financiera": financiera,
    })


@login_required
def asignar_financiera(request, venta_id):
    """Asigna (o desasigna) la financiera que asumió la deuda de una venta
    financiada, desde el listado del módulo Financiación."""
    from ventas.models import Venta

    venta = get_object_or_404(Venta, pk=venta_id)
    if request.method == "POST":
        financiera_id = (request.POST.get("financiera") or "").strip()
        if financiera_id:
            venta.financiera = get_object_or_404(Financiera, pk=financiera_id)
        else:
            venta.financiera = None
        venta.save(update_fields=["financiera"])
        messages.success(request, "Financiera asignada a la venta.")
    return redirect("financiacion:index")

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone

from .models import GastoPersonal
from .forms import GastoPersonalForm
from .decorators import solo_gestion_personal


@solo_gestion_personal
def lista_gastos(request):
    # Cada usuario ve solo sus propios gastos personales.
    gastos = GastoPersonal.objects.filter(usuario=request.user)
    hoy = timezone.now().date()
    total_mes = gastos.filter(
        fecha__year=hoy.year, fecha__month=hoy.month
    ).aggregate(t=Sum("monto"))["t"] or 0
    total_general = gastos.aggregate(t=Sum("monto"))["t"] or 0
    return render(request, "gastos_personales/lista.html", {
        "gastos": gastos,
        "total_mes": total_mes,
        "total_general": total_general,
        "hoy": hoy,
    })


@solo_gestion_personal
def crear_gasto(request):
    if request.method == "POST":
        form = GastoPersonalForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.usuario = request.user
            gasto.save()
            messages.success(request, "Gasto personal agregado correctamente.")
            return redirect("gastos_personales:lista")
    else:
        form = GastoPersonalForm(initial={"fecha": timezone.now().date()})
    return render(request, "gastos_personales/form.html", {"form": form})


@solo_gestion_personal
def editar_gasto(request, pk):
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = GastoPersonalForm(request.POST, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto actualizado correctamente.")
            return redirect("gastos_personales:lista")
    else:
        form = GastoPersonalForm(instance=gasto)
    return render(request, "gastos_personales/form.html", {
        "form": form, "editando": True, "obj": gasto,
    })


@solo_gestion_personal
def eliminar_gasto(request, pk):
    gasto = get_object_or_404(GastoPersonal, pk=pk, usuario=request.user)
    if request.method == "POST":
        gasto.delete()
        messages.success(request, "Gasto eliminado correctamente.")
        return redirect("gastos_personales:lista")
    return render(request, "gastos_personales/eliminar.html", {"obj": gasto})

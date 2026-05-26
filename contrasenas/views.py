from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q

from .models import Contrasena
from .forms import ContrasenaForm
from .decorators import solo_gestion_interna


@solo_gestion_interna
def lista_contrasenas(request):
    query = request.GET.get("q", "").strip()
    contrasenas = Contrasena.objects.all()
    if query:
        contrasenas = contrasenas.filter(
            Q(servicio__icontains=query) | Q(usuario__icontains=query)
        )
    return render(request, "contrasenas/lista.html", {
        "contrasenas": contrasenas,
        "query": query,
    })


@solo_gestion_interna
def crear_contrasena(request):
    if request.method == "POST":
        form = ContrasenaForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creado_por = request.user
            obj.save()
            messages.success(request, "Contraseña guardada correctamente.")
            return redirect("contrasenas:lista")
    else:
        form = ContrasenaForm()
    return render(request, "contrasenas/form.html", {"form": form})


@solo_gestion_interna
def editar_contrasena(request, pk):
    obj = get_object_or_404(Contrasena, pk=pk)
    if request.method == "POST":
        form = ContrasenaForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("contrasenas:lista")
    else:
        form = ContrasenaForm(instance=obj)
    return render(request, "contrasenas/form.html", {
        "form": form,
        "editando": True,
        "obj": obj,
    })


@solo_gestion_interna
def eliminar_contrasena(request, pk):
    obj = get_object_or_404(Contrasena, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Contraseña eliminada correctamente.")
        return redirect("contrasenas:lista")
    return render(request, "contrasenas/eliminar.html", {"obj": obj})

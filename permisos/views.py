from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .access import SECCIONES, SECCION_KEYS, es_admin, _admins
from .models import PermisoUsuario


def solo_admin(view_func):
    @wraps(view_func)
    @login_required(login_url="ingreso")
    def _wrapped(request, *args, **kwargs):
        if not es_admin(request.user):
            messages.error(request, "No tenés permiso para acceder a este módulo.")
            return redirect("inicio")
        return view_func(request, *args, **kwargs)
    return _wrapped


def _usuarios_gestionables():
    admins = _admins()
    return [
        u for u in User.objects.order_by("username")
        if u.username.lower() not in admins and not u.is_superuser
    ]


@solo_admin
def gestionar_permisos(request):
    usuarios = _usuarios_gestionables()

    if request.method == "POST":
        for u in usuarios:
            perm, _ = PermisoUsuario.objects.get_or_create(usuario=u)
            for key in SECCION_KEYS:
                setattr(perm, key, bool(request.POST.get(f"u{u.id}_{key}")))
            perm.save()
        messages.success(request, "Permisos actualizados correctamente.")
        return redirect("permisos:gestionar")

    filas = []
    for u in usuarios:
        perm, _ = PermisoUsuario.objects.get_or_create(usuario=u)
        celdas = [
            {"name": f"u{u.id}_{key}", "checked": getattr(perm, key)}
            for key in SECCION_KEYS
        ]
        filas.append({"usuario": u, "celdas": celdas})

    return render(request, "permisos/lista.html", {
        "filas": filas,
        "secciones": SECCIONES,
    })

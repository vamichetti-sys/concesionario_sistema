from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .access import MODULOS, todas_las_claves, es_admin, _admins
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
    claves_validas = set(todas_las_claves())

    if request.method == "POST":
        for u in usuarios:
            perm, _ = PermisoUsuario.objects.get_or_create(usuario=u)
            seleccionadas = request.POST.getlist(f"u{u.id}")
            perm.claves = [c for c in seleccionadas if c in claves_validas]
            perm.ver_precio = (f"ver_precio_u{u.id}" in request.POST)
            perm.save(update_fields=["claves", "ver_precio"])
        messages.success(request, "Permisos actualizados correctamente.")
        return redirect("permisos:gestionar")

    # Armar la estructura para el template: por usuario, sus módulos/ítems marcados
    filas = []
    for u in usuarios:
        perm, _ = PermisoUsuario.objects.get_or_create(usuario=u)
        permitidas = set(perm.claves or [])
        modulos = []
        for mod in MODULOS:
            items = [
                {"clave": it["clave"], "etiqueta": it["etiqueta"], "checked": it["clave"] in permitidas}
                for it in mod["items"]
            ]
            modulos.append({
                "clave": mod["clave"],
                "etiqueta": mod["etiqueta"],
                "items": items,
                "todos": all(i["checked"] for i in items),
            })
        filas.append({"usuario": u, "modulos": modulos, "ver_precio": perm.ver_precio})

    return render(request, "permisos/lista.html", {"filas": filas})

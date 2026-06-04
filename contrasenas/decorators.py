from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def _usuarios_permitidos():
    # Configurable por settings; por defecto Hamichetti (Hugo) y Vamichetti.
    usuarios = getattr(settings, "USUARIOS_GESTION_INTERNA", ["Hamichetti", "Vamichetti"])
    return {u.lower() for u in usuarios}


def solo_gestion_interna(view_func):
    """
    Restringe el acceso a los usuarios de gestión interna
    (Hamichetti y Vamichetti). Cualquier otro usuario es redirigido
    al inicio con un mensaje de error.
    """
    @wraps(view_func)
    @login_required(login_url="ingreso")
    def _wrapped(request, *args, **kwargs):
        from permisos.access import puede_ver_clave
        if not puede_ver_clave(request.user, "contrasenas"):
            messages.error(request, "No tenés permiso para acceder a este módulo.")
            return redirect("inicio")
        return view_func(request, *args, **kwargs)
    return _wrapped

from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def _usuarios_permitidos():
    usuarios = getattr(settings, "USUARIOS_GESTION_INTERNA", ["Hamichetti", "Vamichetti"])
    return {u.lower() for u in usuarios}


def solo_gestion_personal(view_func):
    """
    Restringe el acceso a los usuarios de gestión personal
    (Hamichetti y Vamichetti), igual que el resto de Gestión Personal.
    """
    @wraps(view_func)
    @login_required(login_url="ingreso")
    def _wrapped(request, *args, **kwargs):
        if request.user.username.lower() not in _usuarios_permitidos():
            messages.error(request, "No tenés permiso para acceder a este módulo.")
            return redirect("inicio")
        return view_func(request, *args, **kwargs)
    return _wrapped

from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def _usuarios_permitidos():
    usuarios = getattr(settings, "USUARIOS_GESTION_INTERNA", ["Hamichetti", "Vamichetti"])
    return {u.lower() for u in usuarios}


def solo_admins(view_func):
    """
    Acceso según la pantalla de Permisos: los admins (Vamichetti/Hamichetti)
    siempre entran; el resto, solo si tiene tildado 'Agenda de Pagos'.
    """
    @wraps(view_func)
    @login_required(login_url="ingreso")
    def _wrapped(request, *args, **kwargs):
        from permisos.access import puede_ver_clave
        if not puede_ver_clave(request.user, "agenda_pagos"):
            messages.error(request, "No tenés permiso para acceder a este módulo.")
            return redirect("inicio")
        return view_func(request, *args, **kwargs)
    return _wrapped

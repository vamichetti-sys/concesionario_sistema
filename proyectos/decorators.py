from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def solo_usuario_principal(view_func):
    """
    Restringe el acceso a la vista al usuario principal definido en
    settings.USUARIO_PRINCIPAL. Cualquier otro usuario es redirigido
    al inicio con un mensaje de error.
    """
    @wraps(view_func)
    @login_required(login_url='ingreso')
    def _wrapped(request, *args, **kwargs):
        usuario_principal = getattr(settings, 'USUARIO_PRINCIPAL', None)
        if not request.user.is_authenticated or request.user.username != usuario_principal:
            messages.error(
                request,
                'No tenés permiso para acceder a este módulo.',
            )
            return redirect('inicio')
        return view_func(request, *args, **kwargs)
    return _wrapped

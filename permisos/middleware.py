from django.shortcuts import redirect
from django.contrib import messages

from .access import es_admin, puede_ver_url


class PermisosMiddleware:
    """
    Bloquea el acceso por URL a los ítems para los que el usuario no
    tiene permiso. Los admins (Vamichetti/Hamichetti/superuser) pasan
    siempre. Debe ir DESPUÉS de Authentication y Messages middleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not es_admin(user):
            if not puede_ver_url(user, request.path):
                messages.error(
                    request, "No tenés permiso para acceder a esta sección."
                )
                return redirect("inicio")
        return self.get_response(request)

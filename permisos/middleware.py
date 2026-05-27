from django.shortcuts import redirect
from django.contrib import messages

from .access import URL_SECCION, es_admin, puede_ver


class PermisosMiddleware:
    """
    Bloquea el acceso por URL a las secciones para las que el usuario no
    tiene permiso. Los admins (Vamichetti/Hamichetti/superuser) pasan
    siempre. Debe ir DESPUÉS de Authentication y Messages middleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not es_admin(user):
            path = request.path
            for prefix, seccion in URL_SECCION:
                if path.startswith(prefix):
                    if not puede_ver(user, seccion):
                        messages.error(
                            request, "No tenés permiso para acceder a esta sección."
                        )
                        return redirect("inicio")
                    break
        return self.get_response(request)

import threading

_thread_locals = threading.local()


def get_current_request():
    return getattr(_thread_locals, "request", None)


def get_current_user():
    req = get_current_request()
    return getattr(req, "user", None) if req else None


def get_current_ip():
    req = get_current_request()
    if not req:
        return None
    xff = req.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return req.META.get("REMOTE_ADDR")


class AuditoriaMiddleware:
    """
    Guarda el request actual en thread-local para que los signals
    puedan acceder al usuario y la IP.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        try:
            return self.get_response(request)
        finally:
            _thread_locals.request = None


class NoBrowserCacheMiddleware:
    """
    Evita que el navegador cachee páginas para usuarios autenticados.
    Sin esto, el browser muestra versiones viejas cuando otro usuario
    edita los mismos datos.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            content_type = response.get("Content-Type", "")
            if "text/html" in content_type or "application/json" in content_type:
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
        return response

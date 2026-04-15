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

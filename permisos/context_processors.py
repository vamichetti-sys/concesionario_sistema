from .access import secciones_de_usuario


def secciones_permitidas(request):
    """Expone qué secciones puede ver el usuario actual, para el sidebar."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"secciones_permitidas": secciones_de_usuario(user)}

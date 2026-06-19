from .access import permisos_menu, grupos_menu, es_admin, puede_ver_precio


def secciones_permitidas(request):
    """
    Expone al sidebar:
    - permisos_menu: dict {clave_item: bool}
    - grupos_menu:   dict {clave_modulo: bool}  (módulo visible si tiene algún ítem)
    - es_admin:      bool
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "permisos_menu": permisos_menu(user),
        "grupos_menu": grupos_menu(user),
        "es_admin": es_admin(user),
        "puede_ver_precio": puede_ver_precio(user),
    }

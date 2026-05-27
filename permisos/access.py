from django.conf import settings

# Secciones controlables del menú (clave -> etiqueta)
SECCIONES = [
    ("operaciones", "Operaciones"),
    ("clientes", "Clientes"),
    ("documentacion", "Documentación"),
    ("administracion", "Administración"),
]
SECCION_KEYS = [k for k, _ in SECCIONES]

# Mapeo de prefijos de URL -> sección, para el bloqueo por middleware.
# Importante: los prefijos llevan barra final para no colisionar
# (ej. "/cuentas/" NO matchea "/cuentas-internas/").
URL_SECCION = [
    ("/vehiculos/", "operaciones"),
    ("/compraventa/", "operaciones"),
    ("/ventas/", "operaciones"),
    ("/presupuestos/", "operaciones"),
    ("/boletos/", "operaciones"),
    ("/reventa/", "operaciones"),
    ("/clientes/", "clientes"),
    ("/cuentas/", "clientes"),
    ("/crm/", "clientes"),
    ("/gestoria/", "documentacion"),
    ("/documentacion/", "documentacion"),
    ("/deudas/", "documentacion"),
    ("/facturacion/", "administracion"),
    ("/asistencia/", "administracion"),
    ("/calendario/", "administracion"),
    ("/community/", "administracion"),
]


def _admins():
    usuarios = getattr(settings, "USUARIOS_GESTION_INTERNA", ["Hamichetti", "Vamichetti"])
    return {u.lower() for u in usuarios}


def es_admin(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and (user.is_superuser or user.username.lower() in _admins())
    )


def permiso_de(user):
    from .models import PermisoUsuario
    perm, _ = PermisoUsuario.objects.get_or_create(usuario=user)
    return perm


def puede_ver(user, seccion):
    if es_admin(user):
        return True
    return getattr(permiso_de(user), seccion, True)


def secciones_de_usuario(user):
    if es_admin(user):
        return {k: True for k in SECCION_KEYS}
    perm = permiso_de(user)
    return {k: getattr(perm, k, True) for k in SECCION_KEYS}

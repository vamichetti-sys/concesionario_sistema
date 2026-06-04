from django.conf import settings

# ==========================================================
# CATÁLOGO DE MÓDULOS E ÍTEMS
# Fuente única de verdad: define el menú, el bloqueo por URL
# y la pantalla de permisos. Cada ítem tiene una clave única.
# ==========================================================
MODULOS = [
    {"clave": "operaciones", "etiqueta": "Operaciones", "items": [
        {"clave": "vehiculos",   "etiqueta": "Vehículos",    "url": "/vehiculos/"},
        {"clave": "compraventa", "etiqueta": "Compra-Venta", "url": "/compraventa/"},
        {"clave": "ventas",      "etiqueta": "Ventas",       "url": "/ventas/"},
        {"clave": "boletos",     "etiqueta": "Boletos",      "url": "/boletos/", "extra": ["/presupuestos/"]},
    ]},
    {"clave": "clientes", "etiqueta": "Clientes", "items": [
        {"clave": "clientes",           "etiqueta": "Clientes",          "url": "/clientes/"},
        {"clave": "cuentas_corrientes", "etiqueta": "Cuentas Corrientes", "url": "/cuentas/"},
        {"clave": "crm",                "etiqueta": "CRM",                "url": "/crm/"},
        {"clave": "reventa",            "etiqueta": "Reventa",            "url": "/reventa/"},
    ]},
    {"clave": "documentacion", "etiqueta": "Documentación", "items": [
        {"clave": "gestoria",      "etiqueta": "Gestoría",      "url": "/gestoria/"},
        {"clave": "documentacion", "etiqueta": "Documentación", "url": "/documentacion/"},
        {"clave": "deudas",        "etiqueta": "Deudas",        "url": "/deudas/"},
    ]},
    {"clave": "administracion", "etiqueta": "Administración", "items": [
        {"clave": "facturacion",     "etiqueta": "Facturación",       "url": "/facturacion/"},
        {"clave": "agenda_pagos",    "etiqueta": "Agenda de Pagos",   "url": "/agenda-pagos/"},
        {"clave": "agenda_ingresos", "etiqueta": "Agenda de Ingresos", "url": "/agenda-ingresos/"},
        {"clave": "asistencia",      "etiqueta": "Asistencia",        "url": "/asistencia/"},
        {"clave": "calendario",      "etiqueta": "Calendario",        "url": "/calendario/"},
    ]},
    {"clave": "gestion_interna", "etiqueta": "Gestión Interna", "items": [
        {"clave": "reportes",             "etiqueta": "Reportes",             "url": "/reportes/"},
        {"clave": "control_stock",        "etiqueta": "Control de Stock",     "url": "/reportes/interno/stock/"},
        {"clave": "cuentas_internas",     "etiqueta": "Cuentas Internas",     "url": "/cuentas-internas/", "extra": ["/cheques/"]},
        {"clave": "gastos_concesionario", "etiqueta": "Gastos Concesionario", "url": "/gastos-mensuales/"},
        {"clave": "auditoria",            "etiqueta": "Auditoría",            "url": "/auditoria/"},
    ]},
    {"clave": "marketing", "etiqueta": "Marketing", "items": [
        {"clave": "marketing", "etiqueta": "Marketing", "url": "/marketing/"},
    ]},
    {"clave": "gestion_personal", "etiqueta": "Gestión Personal", "items": [
        {"clave": "contrasenas",       "etiqueta": "Contraseñas",       "url": "/contrasenas/"},
        {"clave": "gastos_personales", "etiqueta": "Gastos Personales", "url": "/gastos-personales/"},
        {"clave": "financiacion",      "etiqueta": "Financiación",      "url": "/financiacion/"},
    ]},
    {"clave": "panel_personal", "etiqueta": "Panel Personal", "items": [
        {"clave": "proyectos", "etiqueta": "Proyectos", "url": "/proyectos/"},
    ]},
]


def todos_los_items():
    """Lista plana de todos los ítems (con su módulo)."""
    out = []
    for mod in MODULOS:
        for it in mod["items"]:
            out.append({**it, "modulo": mod["clave"]})
    return out


def todas_las_claves():
    return [it["clave"] for it in todos_los_items()]


# Mapa (prefijo_url -> clave) ordenado del más específico al más general,
# para que /reportes/interno/stock/ gane sobre /reportes/.
def _url_clave_map():
    pares = []
    for it in todos_los_items():
        pares.append((it["url"], it["clave"]))
        for extra in it.get("extra", []):
            pares.append((extra, it["clave"]))
    pares.sort(key=lambda p: len(p[0]), reverse=True)
    return pares


URL_CLAVE = _url_clave_map()


# ==========================================================
# ADMINS
# ==========================================================
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


# ==========================================================
# CONSULTAS DE PERMISO
# ==========================================================
def claves_de_usuario(user):
    """Conjunto de claves de ítems que el usuario puede ver."""
    if es_admin(user):
        return set(todas_las_claves())
    perm = permiso_de(user)
    return set(perm.claves or [])


def puede_ver_clave(user, clave):
    if es_admin(user):
        return True
    return clave in (permiso_de(user).claves or [])


def clave_de_url(path):
    """Devuelve la clave del ítem que controla esta URL, o None si no aplica."""
    for prefijo, clave in URL_CLAVE:
        if path.startswith(prefijo):
            return clave
    return None


def puede_ver_url(user, path):
    clave = clave_de_url(path)
    if clave is None:
        return True  # URL no controlada (inicio, logout, etc.)
    return puede_ver_clave(user, clave)


def permisos_menu(user):
    """dict {clave_item: bool} para mostrar/ocultar ítems en el menú."""
    permitidas = claves_de_usuario(user)
    return {c: (c in permitidas) for c in todas_las_claves()}


def grupos_menu(user):
    """dict {clave_modulo: bool} -> True si el usuario ve al menos un ítem del módulo."""
    permitidas = claves_de_usuario(user)
    out = {}
    for mod in MODULOS:
        out[mod["clave"]] = any(it["clave"] in permitidas for it in mod["items"])
    return out

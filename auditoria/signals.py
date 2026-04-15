from django.db.models.signals import post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .middleware import get_current_user, get_current_ip
from .models import LogActividad


# Modelos a auditar: (app_label, model_name, descripcion_extra_func)
MODELOS_AUDITAR = [
    ("vehiculos", "Vehiculo"),
    ("ventas", "Venta"),
    ("cuentas", "CuentaCorriente"),
    ("cuentas", "PlanPago"),
    ("cuentas", "Pago"),
    ("cuentas", "MovimientoCuenta"),
    ("compraventa", "Proveedor"),
    ("compraventa", "CompraVentaOperacion"),
    ("compraventa", "PagoProveedor"),
    ("facturacion", "FacturaRegistrada"),
    ("facturacion", "CompraRegistrada"),
    ("clientes", "Cliente"),
    ("boletos", "BoletoCompraventa"),
    ("gestoria", "Gestoria"),
]


def _desc_obj(instance):
    """Devuelve una descripción del objeto."""
    try:
        return str(instance)[:200]
    except Exception:
        return f"{instance.__class__.__name__} #{instance.pk}"


def _registrar(accion, instance):
    user = get_current_user()
    ip = get_current_ip()
    modelo = instance.__class__.__name__
    desc = _desc_obj(instance)
    LogActividad.registrar(
        usuario=user,
        accion=accion,
        modelo=modelo,
        objeto_id=instance.pk,
        descripcion=f"{modelo}: {desc}",
        ip=ip,
    )


def _handler_save(sender, instance, created, **kwargs):
    # Evitamos infinito: no auditamos el mismo LogActividad
    if sender == LogActividad:
        return
    accion = "crear" if created else "editar"
    try:
        _registrar(accion, instance)
    except Exception:
        pass


def _handler_delete(sender, instance, **kwargs):
    if sender == LogActividad:
        return
    try:
        _registrar("eliminar", instance)
    except Exception:
        pass


def conectar_signals():
    """Conecta signals de save/delete a los modelos críticos."""
    from django.apps import apps
    for app_label, model_name in MODELOS_AUDITAR:
        try:
            Model = apps.get_model(app_label, model_name)
            post_save.connect(_handler_save, sender=Model, weak=False,
                              dispatch_uid=f"audit_save_{app_label}_{model_name}")
            post_delete.connect(_handler_delete, sender=Model, weak=False,
                                dispatch_uid=f"audit_delete_{app_label}_{model_name}")
        except LookupError:
            pass


# ============================================================
# LOGIN / LOGOUT
# ============================================================
@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    ip = None
    if request:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    LogActividad.objects.create(
        usuario=user,
        usuario_texto=user.username,
        accion="login",
        descripcion=f"Inicio de sesión de {user.username}",
        ip=ip,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not user:
        return
    ip = None
    if request:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    LogActividad.objects.create(
        usuario=user,
        usuario_texto=user.username,
        accion="logout",
        descripcion=f"Cierre de sesión de {user.username}",
        ip=ip,
    )


@receiver(user_login_failed)
def log_login_fallido(sender, credentials, request, **kwargs):
    ip = None
    if request:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    username = (credentials or {}).get("username", "desconocido")
    LogActividad.objects.create(
        usuario=None,
        usuario_texto=username,
        accion="login_fallido",
        descripcion=f"Intento de login fallido con usuario: {username}",
        ip=ip,
    )

import threading
from datetime import date, datetime
from decimal import Decimal

from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .middleware import get_current_user, get_current_ip
from .models import LogActividad


# Modelos a auditar: (app_label, model_name)
# NOTA: en cada delete, el handler captura snapshot completo del registro,
# permitiendo recuperar manualmente desde la auditoría si fuera necesario.
MODELOS_AUDITAR = [
    # Vehículos
    ("vehiculos", "Vehiculo"),
    ("vehiculos", "FichaVehicular"),
    ("vehiculos", "FichaTecnica"),
    ("vehiculos", "PagoGastoIngreso"),
    ("vehiculos", "GastoConcesionario"),
    ("vehiculos", "Mantenimiento"),
    # Ventas / Cuentas
    ("ventas", "Venta"),
    ("cuentas", "CuentaCorriente"),
    ("cuentas", "PlanPago"),
    ("cuentas", "CuotaPlan"),
    ("cuentas", "Pago"),
    ("cuentas", "PagoCuota"),
    ("cuentas", "MovimientoCuenta"),
    # Clientes / CRM
    ("clientes", "Cliente"),
    ("crm", "Prospecto"),
    ("crm", "Seguimiento"),
    # Compraventa
    ("compraventa", "Proveedor"),
    ("compraventa", "CompraVentaOperacion"),
    ("compraventa", "DeudaProveedor"),
    ("compraventa", "PagoProveedor"),
    # Facturación
    ("facturacion", "FacturaRegistrada"),
    ("facturacion", "CompraRegistrada"),
    # Boletos / Reservas
    ("boletos", "BoletoCompraventa"),
    ("boletos", "Pagare"),
    ("boletos", "PagareLote"),
    ("boletos", "Reserva"),
    ("boletos", "EntregaDocumentacion"),
    # Reventa
    ("reventa", "Reventa"),
    ("reventa", "CuentaRevendedor"),
    ("reventa", "MovimientoRevendedor"),
    # Cheques / Cuentas internas
    ("cheques", "Cheque"),
    ("cuentas_internas", "CuentaInterna"),
    ("cuentas_internas", "MovimientoInterno"),
    # Gestoría
    ("gestoria", "Gestoria"),
    # Gastos mensuales
    ("gastos_mensuales", "CategoriaGasto"),
    ("gastos_mensuales", "GastoMensual"),
    # Presupuestos
    ("presupuestos", "Presupuesto"),
    # Inicio
    ("inicio", "RecordatorioDashboard"),
    # Asistencia
    ("asistencia", "Empleado"),
]

# Campos que no aportan info útil al diff
CAMPOS_IGNORAR = {
    "id", "creado", "creada", "modificado", "modificada",
    "actualizado", "actualizada", "ultima_modificacion",
    "updated_at", "created_at",
}

# Snapshots del estado previo, por thread
_snapshots = threading.local()


def _get_snapshots():
    if not hasattr(_snapshots, "data"):
        _snapshots.data = {}
    return _snapshots.data


def _serializar(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float, str, bool)):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor)


def _snapshot(instance):
    """Captura un dict con los valores actuales de los campos del instance."""
    data = {}
    try:
        for field in instance._meta.fields:
            name = field.name
            if name in CAMPOS_IGNORAR:
                continue
            try:
                if field.is_relation:
                    val = getattr(instance, name, None)
                    val = str(val) if val is not None else None
                else:
                    val = getattr(instance, name, None)
                data[name] = _serializar(val)
            except Exception:
                continue
    except Exception:
        pass
    return data


def _desc_obj(instance):
    try:
        return str(instance)[:200]
    except Exception:
        return f"{instance.__class__.__name__} #{instance.pk}"


def _verbose_modelo(instance):
    try:
        return str(instance._meta.verbose_name).capitalize()
    except Exception:
        return instance.__class__.__name__


def _verbose_campo(instance, nombre):
    """Devuelve el verbose_name de un campo o el nombre normalizado."""
    try:
        field = instance._meta.get_field(nombre)
        verbose = getattr(field, "verbose_name", None)
        if verbose:
            return str(verbose)
    except Exception:
        pass
    return nombre.replace("_", " ")


def _construir_descripcion(accion, instance, diff_antes=None):
    modelo = _verbose_modelo(instance)
    desc_obj = _desc_obj(instance)
    pk = instance.pk

    if accion == "crear":
        return f"Creó {modelo} «{desc_obj}» (id {pk})"
    if accion == "eliminar":
        return f"Eliminó {modelo} «{desc_obj}» (id {pk})"
    if accion == "editar":
        if diff_antes:
            campos = list(diff_antes.keys())
            etiquetas = [_verbose_campo(instance, c) for c in campos[:5]]
            mas = f" y {len(campos) - 5} más" if len(campos) > 5 else ""
            cambios_txt = ", ".join(etiquetas) + mas
            return (
                f"Editó {modelo} «{desc_obj}» (id {pk}) — "
                f"{len(campos)} campo(s): {cambios_txt}"
            )
        return f"Editó {modelo} «{desc_obj}» (id {pk})"
    return f"{accion} {modelo} «{desc_obj}» (id {pk})"


def _registrar(accion, instance, datos_antes=None, datos_despues=None):
    user = get_current_user()
    ip = get_current_ip()
    modelo = instance.__class__.__name__
    descripcion = _construir_descripcion(accion, instance, datos_antes)
    LogActividad.registrar(
        usuario=user,
        accion=accion,
        modelo=modelo,
        objeto_id=instance.pk,
        descripcion=descripcion,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
        ip=ip,
    )


# ============================================================
# SIGNALS: CAPTURA DE DIFF
# ============================================================
def _handler_pre_save(sender, instance, **kwargs):
    """Guarda snapshot del estado anterior antes de guardar."""
    if sender == LogActividad:
        return
    if not instance.pk:
        return  # creación: no hay estado previo
    try:
        original = sender._default_manager.get(pk=instance.pk)
        _get_snapshots()[(sender, instance.pk)] = _snapshot(original)
    except Exception:
        pass


def _handler_save(sender, instance, created, **kwargs):
    if sender == LogActividad:
        return
    accion = "crear" if created else "editar"
    antes = None
    despues = None

    if not created:
        snap_antes = _get_snapshots().pop((sender, instance.pk), None)
        if snap_antes:
            snap_despues = _snapshot(instance)
            # Sólo campos que efectivamente cambiaron
            diff_antes = {}
            diff_despues = {}
            for campo, val_antes in snap_antes.items():
                val_despues = snap_despues.get(campo)
                if val_antes != val_despues:
                    diff_antes[campo] = val_antes
                    diff_despues[campo] = val_despues
            if diff_antes:
                antes = diff_antes
                despues = diff_despues
            else:
                # No hubo cambios reales: no registramos log
                return
    try:
        _registrar(accion, instance, antes, despues)
    except Exception:
        pass


def _handler_delete(sender, instance, **kwargs):
    if sender == LogActividad:
        return
    try:
        _registrar("eliminar", instance, datos_antes=_snapshot(instance))
    except Exception:
        pass


def conectar_signals():
    """Conecta signals de save/delete a los modelos críticos."""
    from django.apps import apps
    for app_label, model_name in MODELOS_AUDITAR:
        try:
            Model = apps.get_model(app_label, model_name)
            pre_save.connect(
                _handler_pre_save, sender=Model, weak=False,
                dispatch_uid=f"audit_presave_{app_label}_{model_name}",
            )
            post_save.connect(
                _handler_save, sender=Model, weak=False,
                dispatch_uid=f"audit_save_{app_label}_{model_name}",
            )
            post_delete.connect(
                _handler_delete, sender=Model, weak=False,
                dispatch_uid=f"audit_delete_{app_label}_{model_name}",
            )
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

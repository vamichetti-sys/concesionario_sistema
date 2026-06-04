from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

from vehiculos.models import GastoConcesionario, FichaVehicular


def _get_ficha_reporte(vehiculo):
    """Obtiene o crea la FichaReporteInterno del vehiculo."""
    from reportes.models import FichaReporteInterno
    ficha, _ = FichaReporteInterno.objects.get_or_create(vehiculo=vehiculo)
    return ficha


def _get_gasto_reporte_model():
    from reportes.models import GastoReporteInterno
    return GastoReporteInterno


# ==========================================================
# Helpers para Control de Gastos (GastoMensual)
# ==========================================================
CATEGORIA_GASTOS_VEHICULOS = "Gastos de vehículos"


def _get_categoria_vehiculos():
    """
    Devuelve (o crea) la categoría 'Gastos de vehículos' usada para
    espejar los gastos del concesionario en Control de Gastos.
    """
    from gastos_mensuales.models import CategoriaGasto
    cat, _ = CategoriaGasto.objects.get_or_create(
        nombre=CATEGORIA_GASTOS_VEHICULOS,
        defaults={
            "es_fijo": False,
            "activa": True,
            "descripcion": "Espejo automático de gastos cargados a vehículos del concesionario.",
        },
    )
    return cat


def _sync_gastomensual(tag, descripcion, monto, fecha=None):
    """
    Crea / actualiza / elimina un GastoMensual identificado por el tag.
    El tag se guarda al final de la descripción (formato '... [GC#42]').
    Si monto <= 0, elimina el registro.
    """
    from gastos_mensuales.models import GastoMensual

    fecha = fecha or timezone.now().date()
    mes = fecha.month
    anio = fecha.year

    existente = GastoMensual.objects.filter(descripcion__contains=tag).first()

    if monto and monto > 0:
        cat = _get_categoria_vehiculos()
        descripcion_full = f"{descripcion} {tag}"
        if existente:
            existente.descripcion = descripcion_full
            existente.monto = monto
            existente.mes = mes
            existente.anio = anio
            existente.categoria = cat
            existente.save(update_fields=["descripcion", "monto", "mes", "anio", "categoria"])
        else:
            GastoMensual.objects.create(
                categoria=cat,
                descripcion=descripcion_full,
                monto=monto,
                mes=mes,
                anio=anio,
            )
    elif existente:
        existente.delete()


def _delete_gastomensual(tag):
    from gastos_mensuales.models import GastoMensual
    GastoMensual.objects.filter(descripcion__contains=tag).delete()


# ==========================================================
# SYNC: GastoConcesionario → GastoReporteInterno
# ==========================================================
@receiver(post_save, sender=GastoConcesionario)
def sync_gasto_extra_a_reporte(sender, instance, created, **kwargs):
    """
    Al crear/editar un gasto extra:
      1) lo sincroniza en reportes (GastoReporteInterno).
      2) lo refleja automáticamente en Control de Gastos (GastoMensual).
    Usa el tag '[GC#{pk}]' en el concepto/descripción para identificarlo.
    """
    GastoReporteInterno = _get_gasto_reporte_model()
    ficha_reporte = _get_ficha_reporte(instance.vehiculo)

    tag = f"[GC#{instance.pk}]"

    existente = GastoReporteInterno.objects.filter(
        ficha=ficha_reporte,
        concepto__contains=tag,
    ).first()

    concepto = f"{instance.concepto} {tag}"

    if existente:
        existente.concepto = concepto
        existente.monto = instance.monto
        existente.save(update_fields=["concepto", "monto"])
    else:
        GastoReporteInterno.objects.create(
            ficha=ficha_reporte,
            concepto=concepto,
            monto=instance.monto,
        )

    # 🔹 Espejo en Control de Gastos
    patente = getattr(instance.vehiculo, "patente", None) or getattr(instance.vehiculo, "marca", "") or "Vehículo"
    descripcion = f"{instance.concepto} – {patente}"
    _sync_gastomensual(
        tag=tag,
        descripcion=descripcion,
        monto=instance.monto,
        fecha=instance.fecha,
    )


@receiver(post_delete, sender=GastoConcesionario)
def delete_gasto_extra_de_reporte(sender, instance, **kwargs):
    """Al eliminar un gasto extra, lo borra de reportes y de Control de Gastos."""
    GastoReporteInterno = _get_gasto_reporte_model()
    try:
        ficha_reporte = _get_ficha_reporte(instance.vehiculo)
    except Exception:
        ficha_reporte = None

    tag = f"[GC#{instance.pk}]"
    if ficha_reporte:
        GastoReporteInterno.objects.filter(
            ficha=ficha_reporte,
            concepto__contains=tag,
        ).delete()

    # 🔹 Espejo en Control de Gastos
    _delete_gastomensual(tag)


# ==========================================================
# SYNC: FichaVehicular gc_* → GastoReporteInterno
# ==========================================================
CAMPOS_GC = [
    ("gc_service", "Service"),
    ("gc_mecanica", "Mecanica"),
    ("gc_chapa_pintura", "Chapa y pintura"),
    ("gc_tapizado", "Tapizado"),
    ("gc_neumaticos", "Neumaticos"),
    ("gc_vidrios", "Vidrios"),
    ("gc_cerrajeria", "Cerrajeria"),
    ("gc_lavado", "Lavado / Pulido"),
    ("gc_gnc", "GNC"),
    ("gc_grabado_autopartes", "Grabado autopartes"),
    ("gc_vtv", "VTV"),
    ("gc_verificacion", "Verificacion policial"),
    ("gc_patentes", "Patentes"),
    ("gc_otros", "Otros"),
]


@receiver(post_save, sender=FichaVehicular)
def sync_vendedor_a_compraventa(sender, instance, **kwargs):
    """
    Cuando se setea el vendedor (proveedor / agencia) en la ficha
    vehicular, se asegura de que exista una CompraVentaOperacion
    para ese vehículo con ese proveedor. Si ya existe pero con otro
    proveedor, lo actualiza. Si el vendedor está vacío no hace nada
    (no borra la operación existente, para no perder histórico).

    De esta forma el vehículo aparece automáticamente en la pantalla
    de Compra-Venta del proveedor, aunque el precio de compra se cargue
    después desde el flujo regular.
    """
    if not instance.vendedor_id:
        return
    if not instance.vehiculo_id:
        return
    try:
        from compraventa.models import CompraVentaOperacion
    except Exception:
        return

    op, creada = CompraVentaOperacion.objects.get_or_create(
        vehiculo_id=instance.vehiculo_id,
        defaults={
            "origen": CompraVentaOperacion.ORIGEN_PROVEEDOR,
            "proveedor_id": instance.vendedor_id,
            "estado": CompraVentaOperacion.PENDIENTE,
        },
    )
    if not creada and (op.proveedor_id != instance.vendedor_id or op.origen != CompraVentaOperacion.ORIGEN_PROVEEDOR):
        op.proveedor_id = instance.vendedor_id
        op.origen = CompraVentaOperacion.ORIGEN_PROVEEDOR
        op.save(update_fields=["proveedor", "origen"])


@receiver(post_save, sender=FichaVehicular)
def sync_gastos_concesionario_fijos(sender, instance, **kwargs):
    """
    Al guardar la ficha, sincroniza los campos gc_* con GastoReporteInterno.
    Usa tag [GCF:campo] para identificar cada gasto fijo.
    """
    GastoReporteInterno = _get_gasto_reporte_model()
    ficha_reporte = _get_ficha_reporte(instance.vehiculo)

    # Identificador completo del vehículo: marca modelo (dominio)
    _veh = instance.vehiculo
    _ident = " ".join(
        str(x) for x in [getattr(_veh, "marca", ""), getattr(_veh, "modelo", "")] if x
    ).strip()
    _dominio = getattr(_veh, "dominio", "") or getattr(_veh, "patente", "") or ""
    if _dominio:
        _ident = f"{_ident} ({_dominio})".strip() if _ident else str(_dominio)
    patente_vehiculo = _ident or "Vehículo"

    for campo, label in CAMPOS_GC:
        monto = getattr(instance, campo, None) or Decimal("0")
        # tag específico por ficha+campo, para que vehículos distintos
        # no se pisen entre sí en Control de Gastos
        tag_reporte = f"[GCF:{campo}]"
        tag_mensual = f"[GCF:{campo}#{instance.pk}]"

        # ---- Espejo en reportes (FichaReporteInterno) ----
        existente = GastoReporteInterno.objects.filter(
            ficha=ficha_reporte,
            concepto__contains=tag_reporte,
        ).first()

        if monto > 0:
            concepto = f"{label} {tag_reporte}"
            if existente:
                existente.concepto = concepto
                existente.monto = monto
                existente.save(update_fields=["concepto", "monto"])
            else:
                GastoReporteInterno.objects.create(
                    ficha=ficha_reporte,
                    concepto=concepto,
                    monto=monto,
                )
        elif existente:
            existente.delete()

        # ---- Espejo en Control de Gastos (GastoMensual) ----
        _sync_gastomensual(
            tag=tag_mensual,
            descripcion=f"{label} – {patente_vehiculo}",
            monto=monto,
        )

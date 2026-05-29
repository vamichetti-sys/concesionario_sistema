from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
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
# SYNC: GastoConcesionario → GastoReporteInterno
# ==========================================================
@receiver(post_save, sender=GastoConcesionario)
def sync_gasto_extra_a_reporte(sender, instance, created, **kwargs):
    """
    Al crear/editar un gasto extra, lo sincroniza en reportes.
    Usa el tag 'gc_extra_{pk}' en el concepto para identificarlo.
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


@receiver(post_delete, sender=GastoConcesionario)
def delete_gasto_extra_de_reporte(sender, instance, **kwargs):
    """Al eliminar un gasto extra, lo borra de reportes."""
    GastoReporteInterno = _get_gasto_reporte_model()
    try:
        ficha_reporte = _get_ficha_reporte(instance.vehiculo)
    except Exception:
        return

    tag = f"[GC#{instance.pk}]"
    GastoReporteInterno.objects.filter(
        ficha=ficha_reporte,
        concepto__contains=tag,
    ).delete()


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

    for campo, label in CAMPOS_GC:
        monto = getattr(instance, campo, None) or Decimal("0")
        tag = f"[GCF:{campo}]"

        existente = GastoReporteInterno.objects.filter(
            ficha=ficha_reporte,
            concepto__contains=tag,
        ).first()

        if monto > 0:
            concepto = f"{label} {tag}"
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
            # Si el monto es 0, eliminar el gasto del reporte
            existente.delete()

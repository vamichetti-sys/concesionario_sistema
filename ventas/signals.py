from django.db.models.signals import post_save
from django.dispatch import receiver

from ventas.models import Venta
from gestoria.models import Gestoria


@receiver(post_save, sender=Venta)
def crear_gestoria_al_confirmar_venta(sender, instance, **kwargs):
    """
    Garantiza que TODA venta confirmada tenga Gestoría vigente,
    sin depender de ninguna vista.
    """

    if instance.estado != "confirmada":
        return

    if not instance.cliente:
        return

    Gestoria.crear_o_actualizar_desde_venta(
        venta=instance,
        vehiculo=instance.vehiculo,
        cliente=instance.cliente
    )

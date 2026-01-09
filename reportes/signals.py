from django.db.models.signals import post_save
from django.dispatch import receiver

from vehiculos.models import Vehiculo
from .models import FichaReporteInterno


@receiver(post_save, sender=Vehiculo)
def crear_ficha_reporte_interno(sender, instance, created, **kwargs):
    """
    Crea automáticamente la FichaReporteInterno
    cuando se da de alta un Vehiculo.
    """
    if created:
        FichaReporteInterno.objects.create(vehiculo=instance)

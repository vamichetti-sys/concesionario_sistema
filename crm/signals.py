from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q

from vehiculos.models import Vehiculo
from crm.models import Prospecto, NotificacionCRM


@receiver(post_save, sender=Vehiculo)
def notificar_prospectos_match(sender, instance, **kwargs):
    """
    Cuando un vehiculo entra a stock (creacion o cambio de estado),
    busca prospectos activos cuyo vehiculo_interes_texto coincida
    con la marca o modelo del vehiculo, y genera una notificacion.
    """
    if instance.estado != "stock":
        return

    marca = instance.marca.lower().strip()
    modelo = instance.modelo.lower().strip()

    # Buscar prospectos activos con texto libre que matchee
    prospectos = Prospecto.objects.filter(
        etapa__in=["nuevo", "contactado", "en_negociacion", "presupuestado"],
    ).exclude(
        vehiculo_interes_texto__isnull=True,
    ).exclude(
        vehiculo_interes_texto="",
    )

    for prospecto in prospectos:
        texto = prospecto.vehiculo_interes_texto.lower().strip()

        # Verificar si alguna palabra clave del interes matchea con marca o modelo
        palabras = texto.split()
        match = any(
            p in marca or p in modelo or marca in p or modelo in p
            for p in palabras
            if len(p) >= 3  # Ignorar palabras muy cortas
        )

        if not match:
            continue

        # No duplicar: verificar si ya existe notificacion para este par
        existe = NotificacionCRM.objects.filter(
            prospecto=prospecto,
            vehiculo=instance,
        ).exists()

        if existe:
            continue

        NotificacionCRM.objects.create(
            prospecto=prospecto,
            vehiculo=instance,
            mensaje=(
                f"{prospecto.nombre_completo} busca \"{prospecto.vehiculo_interes_texto}\" "
                f"→ Ingreso: {instance.marca} {instance.modelo} ({instance.dominio})"
            ),
        )

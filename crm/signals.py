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

        # Verificar que MARCA coincida Y al menos una palabra del modelo también
        palabras = [p for p in texto.split() if len(p) >= 2]

        # Paso 1: la marca del vehículo debe aparecer en el texto del prospecto
        marca_match = any(
            marca in p or p in marca
            for p in palabras
            if len(p) >= 3
        )

        if not marca_match:
            continue

        # Paso 2: al menos una palabra del texto (excluyendo marca y años)
        # debe coincidir con el modelo del vehículo
        palabras_sin_marca = [
            p for p in palabras
            if p not in marca and marca not in p and not p.replace("/", "").isdigit()
        ]

        modelo_match = any(
            p in modelo or modelo in p
            for p in palabras_sin_marca
            if len(p) >= 2
        )

        # Si no hay palabras de modelo para comparar (ej: solo puso "Chevrolet"),
        # aceptar el match por marca solamente
        if palabras_sin_marca and not modelo_match:
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

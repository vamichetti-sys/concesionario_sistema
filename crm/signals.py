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
    con la marca Y modelo del vehiculo, y genera una notificacion.
    """
    if instance.estado != "stock":
        return

    marca = instance.marca.lower().strip()
    modelo = instance.modelo.lower().strip()
    palabras_modelo = [p for p in modelo.split() if len(p) >= 2]

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
        palabras = [p for p in texto.split() if len(p) >= 2]

        # Paso 1: la marca del vehículo debe aparecer en el texto del prospecto
        marca_match = marca in texto

        if not marca_match:
            continue

        # Paso 2: extraer palabras del prospecto que no sean la marca ni años
        palabras_busqueda = [
            p for p in palabras
            if p != marca and not p.replace("/", "").replace("-", "").isdigit()
        ]

        # Si el prospecto solo puso la marca (ej: "Chevrolet"), matchear todo
        if not palabras_busqueda:
            pass
        else:
            # Al menos una palabra de búsqueda debe coincidir EXACTAMENTE
            # con una palabra del modelo del vehículo (no substring parcial)
            modelo_match = any(
                p_busq == p_mod or
                (len(p_busq) >= 3 and (p_busq in p_mod or p_mod in p_busq))
                for p_busq in palabras_busqueda
                for p_mod in palabras_modelo
            )

            if not modelo_match:
                continue

        # No duplicar
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

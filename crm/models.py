from django.db import models
from django.contrib.auth.models import User

from clientes.models import Cliente
from vehiculos.models import Vehiculo


# ============================================================
# PROSPECTO (LEAD)
# ============================================================
class Prospecto(models.Model):

    ORIGEN_CHOICES = [
        ("whatsapp", "WhatsApp"),
        ("telefono", "Teléfono"),
        ("presencial", "Presencial"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("mercadolibre", "MercadoLibre"),
        ("referido", "Referido"),
        ("otro", "Otro"),
    ]

    ETAPA_CHOICES = [
        ("nuevo", "Nuevo"),
        ("contactado", "Contactado"),
        ("en_negociacion", "En negociación"),
        ("presupuestado", "Presupuestado"),
        ("ganado", "Ganado"),
        ("perdido", "Perdido"),
    ]

    PRIORIDAD_CHOICES = [
        ("alta", "Alta"),
        ("media", "Media"),
        ("baja", "Baja"),
    ]

    # Datos del prospecto
    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Origen y seguimiento
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default="whatsapp",
    )
    etapa = models.CharField(
        max_length=20,
        choices=ETAPA_CHOICES,
        default="nuevo",
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default="media",
    )

    # Vehículo de interés
    vehiculo_interes = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospectos",
        verbose_name="Vehículo de interés",
    )
    vehiculo_interes_texto = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Vehículo de interés (texto libre)",
        help_text="Si el vehículo no está en stock",
    )

    # Conversión
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospectos",
        verbose_name="Cliente convertido",
    )

    # Responsable
    asignado_a = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospectos_asignados",
    )

    observaciones = models.TextField(blank=True, null=True)

    # Fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_proximo_contacto = models.DateField(
        null=True,
        blank=True,
        verbose_name="Próximo contacto",
    )

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Prospecto"
        verbose_name_plural = "Prospectos"

    def __str__(self):
        return f"{self.nombre_completo} – {self.get_etapa_display()}"

    @property
    def es_activo(self):
        return self.etapa not in ("ganado", "perdido")

    @property
    def cantidad_seguimientos(self):
        return self.seguimientos.count()


# ============================================================
# SEGUIMIENTO (INTERACCIONES)
# ============================================================
class Seguimiento(models.Model):

    TIPO_CHOICES = [
        ("llamada", "Llamada"),
        ("whatsapp", "WhatsApp"),
        ("visita", "Visita"),
        ("email", "Email"),
        ("nota", "Nota interna"),
    ]

    prospecto = models.ForeignKey(
        Prospecto,
        on_delete=models.CASCADE,
        related_name="seguimientos",
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="whatsapp",
    )

    descripcion = models.TextField(verbose_name="Descripción")

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Seguimiento"
        verbose_name_plural = "Seguimientos"

    def __str__(self):
        return f"{self.get_tipo_display()} – {self.prospecto.nombre_completo}"

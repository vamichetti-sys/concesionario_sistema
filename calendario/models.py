from django.db import models
from vehiculos.models import Vehiculo


class Evento(models.Model):
    # =====================================
    # DATOS BÁSICOS
    # =====================================
    titulo = models.CharField(max_length=255)
    fecha = models.DateField()
    descripcion = models.TextField(blank=True, null=True)

    # =====================================
    # VÍNCULO CON VEHÍCULO
    # =====================================
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="eventos_calendario"
    )

    # =====================================
    # TIPO DE EVENTO
    # =====================================
    TIPO_CHOICES = [
        ("vtv", "Turno VTV"),
        ("autopartes", "Turno Grabado de Autopartes"),
    ]

    tipo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=TIPO_CHOICES
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 📅 Orden lógico por fecha (no rompe consultas existentes)
        ordering = ["fecha"]

    def __str__(self):
        if self.vehiculo:
            return f"{self.titulo} - {self.vehiculo} ({self.fecha})"
        return f"{self.titulo} - {self.fecha}"

    # ======================================================
    # 🔍 HELPERS (NO ROMPEN NADA)
    # ======================================================
    @property
    def es_vtv(self):
        return self.tipo == "vtv"

    @property
    def es_autopartes(self):
        return self.tipo == "autopartes"

    @property
    def tiene_vehiculo(self):
        return self.vehiculo is not None

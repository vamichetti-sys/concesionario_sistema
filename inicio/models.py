from django.db import models
from django.contrib.auth.models import User


class RecordatorioDashboard(models.Model):
    PRIORIDAD_CHOICES = [
        ("alta", "Alta"),
        ("normal", "Normal"),
        ("baja", "Baja"),
    ]

    texto = models.CharField(max_length=300)
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default="normal",
    )
    completado = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recordatorios",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completado", "-prioridad", "-fecha_creacion"]
        verbose_name = "Recordatorio"
        verbose_name_plural = "Recordatorios"

    def __str__(self):
        return self.texto[:50]

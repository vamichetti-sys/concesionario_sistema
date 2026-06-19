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


class CuentaBancaria(models.Model):
    """Cuentas bancarias propias (ej. las de Hugo): banco, nº de cuenta y CBU."""
    titular = models.CharField("Titular", max_length=100, default="Hugo")
    banco = models.CharField("Banco", max_length=120)
    numero_cuenta = models.CharField("Número de cuenta", max_length=80, blank=True)
    cbu = models.CharField("CBU", max_length=40, blank=True)
    alias = models.CharField("Alias", max_length=80, blank=True)
    titular_cuenta = models.CharField("Titular de la cuenta", max_length=140, blank=True)
    observaciones = models.TextField("Observaciones", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titular", "banco"]
        verbose_name = "Cuenta bancaria"
        verbose_name_plural = "Cuentas bancarias"

    def __str__(self):
        return f"{self.banco} — {self.titular}"

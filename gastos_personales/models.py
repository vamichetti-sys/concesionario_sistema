from django.db import models
from django.contrib.auth.models import User


class GastoPersonal(models.Model):
    """
    Gasto personal de un usuario. Cada usuario ve y gestiona solo los
    propios (filtrado por `usuario` en las vistas).
    """
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="gastos_personales"
    )
    fecha = models.DateField("Fecha")
    concepto = models.CharField("Concepto", max_length=200)
    categoria = models.CharField("Categoría", max_length=100, blank=True)
    monto = models.DecimalField("Monto", max_digits=12, decimal_places=2)
    notas = models.TextField("Notas", blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "Gasto personal"
        verbose_name_plural = "Gastos personales"

    def __str__(self):
        return f"{self.concepto} - ${self.monto}"

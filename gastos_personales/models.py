from django.db import models
from django.contrib.auth.models import User

from gastos_mensuales.models import CategoriaGasto


class GastoPersonal(models.Model):
    """
    Gasto personal de un usuario, con la misma estructura que el Control de
    Gastos (categoría fija/variable, mes/año, pagado), pero PRIVADO por
    usuario: cada uno ve y gestiona solo los propios.
    """
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="gastos_personales"
    )
    categoria = models.ForeignKey(
        CategoriaGasto, on_delete=models.PROTECT, related_name="gastos_personales",
        null=True, blank=True,  # nullable a nivel DB para migrar filas viejas; el form lo exige.
    )
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mes = models.PositiveSmallIntegerField(default=1)
    anio = models.PositiveIntegerField(default=2026)
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-anio", "-mes", "categoria__nombre"]
        verbose_name = "Gasto personal"
        verbose_name_plural = "Gastos personales"

    def __str__(self):
        return f"{self.categoria.nombre} – ${self.monto} ({self.mes}/{self.anio})"


class IngresoPersonal(models.Model):
    """Ingreso personal privado por usuario — separado de los gastos."""
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ingresos_personales"
    )
    concepto = models.CharField("Concepto", max_length=150,
                                help_text="Ej: Sueldo, Venta, Alquiler cobrado, Otro")
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mes = models.PositiveSmallIntegerField(default=1)
    anio = models.PositiveIntegerField(default=2026)
    fecha = models.DateField("Fecha", null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-anio", "-mes", "concepto"]
        verbose_name = "Ingreso personal"
        verbose_name_plural = "Ingresos personales"

    def __str__(self):
        return f"{self.concepto} – ${self.monto} ({self.mes}/{self.anio})"

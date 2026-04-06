from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


# ============================================================
# CATEGORIA DE GASTO
# ============================================================
class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    es_fijo = models.BooleanField(
        default=False,
        help_text="Indica si es un gasto fijo mensual (alquiler, sueldos, etc.)",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoria de gasto"
        verbose_name_plural = "Categorias de gastos"

    def __str__(self):
        tipo = "Fijo" if self.es_fijo else "Variable"
        return f"{self.nombre} ({tipo})"


# ============================================================
# GASTO MENSUAL
# ============================================================
class GastoMensual(models.Model):

    UNIDAD_CHOICES = [
        ("HA", "Hamichetti"),
        ("VA", "Vamichetti"),
        ("ambas", "Ambas"),
    ]

    categoria = models.ForeignKey(
        CategoriaGasto,
        on_delete=models.PROTECT,
        related_name="gastos",
    )

    descripcion = models.CharField(max_length=200, blank=True, null=True)

    monto = models.DecimalField(max_digits=12, decimal_places=2)

    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()

    unidad = models.CharField(
        max_length=5,
        choices=UNIDAD_CHOICES,
        default="ambas",
    )

    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)

    observaciones = models.TextField(blank=True, null=True)

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-anio", "-mes", "categoria__nombre"]
        verbose_name = "Gasto mensual"
        verbose_name_plural = "Gastos mensuales"

    def __str__(self):
        return f"{self.categoria.nombre} – ${self.monto} ({self.mes}/{self.anio})"


# ============================================================
# RESUMEN MENSUAL DE GASTOS (CACHE/CIERRE)
# ============================================================
class ResumenGastosMensual(models.Model):
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()

    total_fijos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_variables = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_general = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pagado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pendiente = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("mes", "anio")
        ordering = ["-anio", "-mes"]

    def __str__(self):
        return f"Resumen {self.mes}/{self.anio} – ${self.total_general}"

    def recalcular(self):
        gastos = GastoMensual.objects.filter(mes=self.mes, anio=self.anio)

        self.total_fijos = gastos.filter(
            categoria__es_fijo=True
        ).aggregate(t=models.Sum("monto"))["t"] or Decimal("0")

        self.total_variables = gastos.filter(
            categoria__es_fijo=False
        ).aggregate(t=models.Sum("monto"))["t"] or Decimal("0")

        self.total_general = self.total_fijos + self.total_variables

        self.total_pagado = gastos.filter(
            pagado=True
        ).aggregate(t=models.Sum("monto"))["t"] or Decimal("0")

        self.total_pendiente = self.total_general - self.total_pagado

        self.save()

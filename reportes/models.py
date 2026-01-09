from django.db import models
from vehiculos.models import Vehiculo


# ==========================================================
# REPORTE MENSUAL
# Guarda el cierre mensual del sistema
# (facturación + ganancia)
# ==========================================================
class ReporteMensual(models.Model):

    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField()  # 1 a 12

    total_facturado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    # 🆕 GANANCIA MENSUAL GUARDADA
    ganancia_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Ganancia mensual"
    )

    fecha_cierre = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha en la que se realizó el cierre mensual"
    )

    class Meta:
        unique_together = ("anio", "mes")
        ordering = ["-anio", "-mes"]
        verbose_name = "Reporte Mensual"
        verbose_name_plural = "Reportes Mensuales"

    def __str__(self):
        return f"Reporte {self.mes}/{self.anio}"


# ==========================================================
# REPORTE ANUAL
# Guarda el cierre anual consolidado
# ==========================================================
class ReporteAnual(models.Model):

    anio = models.PositiveIntegerField(unique=True)

    total_facturado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    # 🆕 GANANCIA ANUAL GUARDADA
    ganancia_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Ganancia anual"
    )

    fecha_cierre = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha en la que se realizó el cierre anual"
    )

    class Meta:
        ordering = ["-anio"]
        verbose_name = "Reporte Anual"
        verbose_name_plural = "Reportes Anuales"

    def __str__(self):
        return f"Reporte Anual {self.anio}"


# ==========================================================
# FICHA INTERNA DE REPORTE (AUTOMÁTICA)
# Control económico interno por vehículo
# ==========================================================
class FichaReporteInterno(models.Model):

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="ficha_reporte"
    )

    # ----------------------
    # COMPRA
    # ----------------------
    fecha_compra = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de compra"
    )

    precio_compra = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Precio de compra"
    )

    # ----------------------
    # VENTA
    # ----------------------
    fecha_venta = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de venta"
    )

    precio_venta = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Precio de venta"
    )

    comprador = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Comprador"
    )

    # ----------------------
    # AUDITORÍA
    # ----------------------
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    # ----------------------
    # CÁLCULOS AUTOMÁTICOS
    # ----------------------
    @property
    def total_gastos_calculado(self):
        """
        Suma automática de todos los gastos cargados
        en el reporte interno.
        """
        return sum(g.monto for g in self.gastos.all())

    @property
    def ganancia(self):
        """
        Ganancia real del vehículo (dinámica):
        venta - compra - gastos
        """
        if self.precio_compra and self.precio_venta:
            return (
                self.precio_venta
                - self.precio_compra
                - self.total_gastos_calculado
            )
        return None

    def __str__(self):
        return f"Ficha interna {self.vehiculo}"


# ==========================================================
# GASTOS INTERNOS DEL REPORTE
# Cada gasto es un registro independiente
# ==========================================================
class GastoReporteInterno(models.Model):

    ficha = models.ForeignKey(
        FichaReporteInterno,
        on_delete=models.CASCADE,
        related_name="gastos"
    )

    concepto = models.CharField(
        max_length=200,
        verbose_name="Concepto"
    )

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto"
    )

    fecha = models.DateField(
        auto_now_add=True,
        verbose_name="Fecha"
    )

    def __str__(self):
        return f"{self.concepto} – ${self.monto}"

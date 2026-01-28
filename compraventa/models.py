from django.db import models
from django.utils import timezone
from decimal import Decimal

from vehiculos.models import Vehiculo


# ==========================================================
# 🏢 PROVEEDOR / AGENCIA
# ==========================================================
class Proveedor(models.Model):
    nombre_empresa = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Nombre de la empresa"
    )

    cuit = models.CharField(
        max_length=13,
        unique=True,
        default="00-00000000-0",
    )

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["nombre_empresa"]

    def __str__(self):
        return f"{self.nombre_empresa} ({self.cuit})"

    @property
    def deuda_total(self) -> Decimal:
        total = Decimal("0")
        for d in self.deudas.all():
            total += d.saldo
        return total


# ==========================================================
# 🔁 COMPRA / INGRESO DE VEHÍCULO
# ==========================================================
class CompraVentaOperacion(models.Model):
    ORIGEN_PROVEEDOR = "PROVEEDOR"
    ORIGEN_CLIENTE = "CLIENTE"
    ORIGEN_DIRECTA = "DIRECTA"

    ORIGEN_CHOICES = [
        (ORIGEN_PROVEEDOR, "Proveedor / Agencia"),
        (ORIGEN_CLIENTE, "Cliente"),
        (ORIGEN_DIRECTA, "Compra directa"),
    ]

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.PROTECT,   # ⛔ NO tocamos esto
        related_name="operacion_compra",
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default=ORIGEN_PROVEEDOR
    )

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,   # ✅ CAMBIO CLAVE
        related_name="operaciones",
        blank=True,
        null=True,
        help_text="Obligatorio si origen = PROVEEDOR",
    )

    fecha_compra = models.DateField(default=timezone.now)
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos_ingreso = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    PENDIENTE = "PENDIENTE"
    PUBLICADO = "PUBLICADO"
    VENDIDO = "VENDIDO"
    CERRADO = "CERRADO"

    ESTADO_CHOICES = [
        (PENDIENTE, "Pendiente"),
        (PUBLICADO, "Publicado"),
        (VENDIDO, "Vendido"),
        (CERRADO, "Cerrado"),
    ]

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=PENDIENTE
    )

    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Compra {self.vehiculo} ({self.get_origen_display()})"


# ==========================================================
# 💸 DEUDA POR VEHÍCULO
# ==========================================================
class DeudaProveedor(models.Model):
    """
    Representa la deuda de un proveedor por UNA unidad (vehículo).
    La deuda nace al registrar la compra y es SOLO por el precio de compra.
    Los gastos de ingreso NO forman parte de esta deuda.
    """

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,   # ✅ CAMBIO CLAVE
        related_name="deudas"
    )

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.PROTECT,   # ⛔ NO tocamos esto
        related_name="deuda_proveedor"
    )

    monto_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "Deuda de proveedor"
        verbose_name_plural = "Deudas de proveedores"

    def __str__(self):
        return f"Deuda {self.proveedor.nombre_empresa} - {self.vehiculo}"

    # ======================================================
    # 💳 TOTAL PAGADO
    # ======================================================
    @property
    def monto_pagado(self) -> Decimal:
        agg = self.pagos.aggregate(models.Sum("monto"))
        return agg["monto__sum"] or Decimal("0")

    # ======================================================
    # 🔴 SALDO ADEUDADO
    # ======================================================
    @property
    def saldo(self) -> Decimal:
        return (self.monto_total or Decimal("0")) - self.monto_pagado


# ==========================================================
# 💰 PAGOS A PROVEEDOR
# ==========================================================
class PagoProveedor(models.Model):
    deuda = models.ForeignKey(
        DeudaProveedor,
        on_delete=models.CASCADE,
        related_name="pagos"
    )

    fecha = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nota = models.CharField(max_length=200, blank=True, null=True)
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pago {self.deuda.proveedor.nombre_empresa} - ${self.monto}"

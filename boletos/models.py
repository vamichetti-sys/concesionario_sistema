from django.db import models
from decimal import Decimal
from django.utils.timezone import now

from clientes.models import Cliente
from vehiculos.models import Vehiculo
from ventas.models import Venta
from cuentas.models import CuentaCorriente


# ==========================================================
# BOLETO DE COMPRAVENTA (EXISTENTE – NO TOCAR)
# ==========================================================
class BoletoCompraventa(models.Model):

    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="boletos"
    )

    cuenta_corriente = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="boletos"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="boletos"
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="boletos",
        null=True,
        blank=True
    )

    numero = models.PositiveIntegerField()
    texto_final = models.TextField()

    pdf = models.FileField(
        upload_to="boletos/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Boleto #{self.numero} - {self.cliente}"


from django.db import models
from django.utils.timezone import now
from decimal import Decimal

class PagareLote(models.Model):

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pagares_lotes"
    )

    beneficiario = models.CharField(
        max_length=255,
        default="AMICHETTI HUGO ALBERTO"
    )

    lugar_emision = models.CharField(
        max_length=100,
        default="Rojas"
    )

    fecha_emision = models.DateField(default=now)

    monto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00")
    )

    cantidad = models.PositiveIntegerField(default=1)

    pdf = models.FileField(
        upload_to="pagares/lotes/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Lote de pagarés ({self.cantidad}) - {self.cliente}"


# ==========================================================
# PAGARÉ (INDIVIDUAL – LEGAL)
# ==========================================================
class Pagare(models.Model):

    lote = models.ForeignKey(
        PagareLote,
        on_delete=models.CASCADE,
        related_name="pagares",
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pagares"
    )

    numero = models.PositiveIntegerField(unique=True)

    beneficiario = models.CharField(
        max_length=255,
        default="AMICHETTI HUGO ALBERTO"
    )

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00")
    )

    lugar_emision = models.CharField(
        max_length=100,
        default="Rojas"
    )

    fecha_emision = models.DateField(default=now)

    fecha_vencimiento = models.DateField(
        null=True,
        blank=True
    )

    # ✅ CAMPO NECESARIO PARA GUARDAR EL PDF DEL PAGARÉ
    pdf = models.FileField(
        upload_to="pagares/",
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Pagaré #{self.numero} - {self.cliente} - ${self.monto}"

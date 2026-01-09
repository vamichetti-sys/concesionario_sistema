from django.db import models
from decimal import Decimal
from ventas.models import Venta


# ==========================================================
# FACTURA REGISTRADA (CONTROL CONTABLE)
# ==========================================================
class FacturaRegistrada(models.Model):
    """
    Este modelo NO emite factura al cliente.
    Sirve únicamente para:
    - control contable interno
    - cálculo de facturación mensual / anual
    - información para el contador
    """

    # Relación con la venta (opcional pero recomendada)
    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        related_name="facturas",
        null=True,
        blank=True
    )

    # Número de factura / comprobante
    numero = models.CharField(
        max_length=50,
        help_text="Número de factura / comprobante"
    )

    fecha = models.DateField(
        help_text="Fecha de la factura"
    )

    # ======================================================
    # 💰 IMPORTES
    # ======================================================

    # 🔹 MONTO NETO (sin IVA)
    monto_neto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monto neto sin IVA"
    )

    # 🔹 IVA (%)
    iva_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("21.00"),
        help_text="Porcentaje de IVA aplicado"
    )

    # 🔹 IVA CALCULADO
    monto_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monto de IVA calculado"
    )

    # 🔹 MONTO TOTAL FACTURADO
    # ⚠️ Campo histórico: NO SE ELIMINA
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Monto total facturado (neto + IVA)"
    )

    # ======================================================
    # ESTADO CONTABLE
    # ======================================================
    ESTADOS = [
        ("valida", "Válida"),
        ("anulada", "Anulada"),
    ]

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="valida"
    )

    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Factura registrada"
        verbose_name_plural = "Facturas registradas"

        indexes = [
            models.Index(fields=["numero"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        if self.venta:
            return f"Factura {self.numero} - Venta {self.venta.id}"
        return f"Factura {self.numero}"

    # ======================================================
    # 🔍 HELPERS CONTABLES (NO ROMPEN NADA)
    # ======================================================
    @property
    def es_valida(self):
        return self.estado == "valida"

    @property
    def es_anulada(self):
        return self.estado == "anulada"

    # ======================================================
    # 🧠 CÁLCULOS AUTOMÁTICOS
    # ======================================================
    def calcular_iva(self):
        """
        Calcula IVA y monto total a partir del monto neto.
        No rompe facturas antiguas.
        """
        if self.monto_neto is not None:
            iva = (self.monto_neto * self.iva_porcentaje) / Decimal("100")
            self.monto_iva = iva.quantize(Decimal("0.01"))
            self.monto = (self.monto_neto + self.monto_iva).quantize(Decimal("0.01"))

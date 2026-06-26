from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from vehiculos.models import Vehiculo
from clientes.models import Cliente


# ==========================================================
# VENTA
# ==========================================================
class Venta(models.Model):

    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("revertida", "Revertida"),
    ]

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.SET_NULL,
        related_name="venta",
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="ventas",
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )

    fecha_venta = models.DateField(
        auto_now_add=True
    )

    precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    vendido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="ventas_realizadas",
        null=True,
        blank=True,
        verbose_name="Vendido por",
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Venta {self.id} - {self.vehiculo or 'Sin vehículo'} - {self.cliente or 'Sin cliente'}"

    # ======================================================
    # CONFIRMACIÓN CENTRALIZADA
    # ======================================================
    def confirmar(self):
        """
        Confirma la venta de forma segura y consistente.
        - Copia el precio del vehículo si no estaba cargado
        - Marca la venta como confirmada
        - Crea la cuenta corriente si no existe
        """

        from cuentas.models import CuentaCorriente, MovimientoCuenta

        cuenta = None
        if self.cliente:
            cuenta, _ = CuentaCorriente.objects.get_or_create(
                venta=self,
                defaults={"cliente": self.cliente}
            )

            # ✅ FIX: Si la cuenta existía y estaba cerrada, reabrir
            if cuenta.estado == "cerrada":
                cuenta.estado = "al_dia"
                cuenta.cliente = self.cliente
                cuenta.save(update_fields=["estado", "cliente"])

        if self.precio_venta is None and self.vehiculo:
            self.precio_venta = self.vehiculo.precio

        if self.estado != "confirmada":
            self.estado = "confirmada"
            self.save(update_fields=["estado", "precio_venta"])
        else:
            self.save(update_fields=["precio_venta"])

        return self

    # ======================================================
    # ADJUDICACIÓN COMPLETA
    # ======================================================
    def adjudicar_cliente(self, cliente):
        """
        Se llama cuando se asigna un cliente a la venta.
        Garantiza que:
        - la venta quede confirmada
        - exista Cuenta Corriente
        - exista Gestoría
        """

        from cuentas.models import CuentaCorriente
        from gestoria.models import Gestoria

        # ==================================================
        # 1️⃣ ASIGNAR CLIENTE A LA VENTA
        # ==================================================
        self.cliente = cliente
        self.save(update_fields=["cliente"])

        # ==================================================
        # 2️⃣ CREAR O RECUPERAR CUENTA CORRIENTE
        # ==================================================
        cuenta, creada = CuentaCorriente.objects.get_or_create(
            venta=self,
            defaults={"cliente": cliente}
        )

        # ✅ FIX: Si la cuenta ya existía (cerrada por reversión),
        # reabrirla y limpiar movimientos viejos
        if not creada and cuenta.estado == "cerrada":
            cuenta.estado = "al_dia"
            cuenta.saldo = 0
            cuenta.cliente = cliente
            cuenta.save(update_fields=["estado", "saldo", "cliente"])

            # Limpiar movimientos huérfanos del plan anterior
            cuenta.movimientos.all().delete()

        # ==================================================
        # 3️⃣ CONFIRMAR VENTA
        # ==================================================
        self.confirmar()

        # ==================================================
        # 4️⃣ SINCRONIZAR CLIENTE EN CUENTA CORRIENTE
        # ==================================================
        if cuenta.cliente != cliente:
            cuenta.cliente = cliente
            cuenta.save(update_fields=["cliente"])

        # ==================================================
        # 5️⃣ CREAR / ACTUALIZAR GESTORÍA
        # ==================================================
        gestoria = Gestoria.crear_o_actualizar_desde_venta(
            venta=self,
            vehiculo=self.vehiculo,
            cliente=cliente
        )

        gestoria.save()

        return self


# ==========================================================
# CUENTA CORRIENTE DE COMISIONES POR VENDEDOR
# ==========================================================
class CuentaVendedor(models.Model):
    """
    Cuenta corriente de un vendedor para llevar sus comisiones.

    Convención de saldo:
        saldo = comisiones generadas (haber) - pagos realizados (debe)
    Un saldo positivo es lo que la agencia todavía le debe al vendedor.
    """

    vendedor = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cuenta_comisiones",
        verbose_name="Vendedor",
    )

    saldo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vendedor__first_name", "vendedor__username"]
        verbose_name = "Cuenta de vendedor (comisiones)"
        verbose_name_plural = "Cuentas de vendedores (comisiones)"

    def __str__(self):
        nombre = self.vendedor.get_full_name() or self.vendedor.username
        return f"{nombre} – Saldo: ${self.saldo}"

    def recalcular_saldo(self):
        from django.db.models import Sum
        comisiones = self.movimientos.filter(tipo="comision").aggregate(
            t=Sum("monto")
        )["t"] or Decimal("0")
        pagos = self.movimientos.filter(tipo="pago").aggregate(
            t=Sum("monto")
        )["t"] or Decimal("0")
        self.saldo = comisiones - pagos
        self.save(update_fields=["saldo"])


class MovimientoComision(models.Model):
    TIPOS = [
        ("comision", "Comisión generada"),
        ("pago", "Pago al vendedor"),
    ]

    cuenta = models.ForeignKey(
        CuentaVendedor,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    descripcion = models.CharField(max_length=255, blank=True)
    fecha = models.DateField(auto_now_add=True)
    venta = models.ForeignKey(
        Venta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_comision",
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "Movimiento de comisión"
        verbose_name_plural = "Movimientos de comisión"

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.monto} – {self.cuenta}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cuenta.recalcular_saldo()

    def delete(self, *args, **kwargs):
        cuenta = self.cuenta
        super().delete(*args, **kwargs)
        cuenta.recalcular_saldo()


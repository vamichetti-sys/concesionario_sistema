from django.db import models
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


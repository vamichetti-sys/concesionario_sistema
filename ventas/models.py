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
    ]

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="venta"
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

    # 📅 Campo CLAVE para reportes mensuales/anuales
    fecha_venta = models.DateField(
        auto_now_add=True
    )

    # 💰 Campo CLAVE para totales de reportes
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
        return f"Venta {self.id} - {self.vehiculo} - {self.cliente or 'Sin cliente'}"

    # ======================================================
    # 🔒 CONFIRMACIÓN CENTRALIZADA (NUEVO – NO ROMPE NADA)
    # ======================================================
    def confirmar(self):
        """
        Confirma la venta de forma segura y consistente.
        - Copia el precio del vehículo si no estaba cargado
        - Marca la venta como confirmada
        - Crea la cuenta corriente si no existe
        - Imputa la deuda inicial UNA sola vez
        """

        from cuentas.models import CuentaCorriente, MovimientoCuenta

        # 🔒 Evitar doble ejecución
        if self.estado == "confirmada":
            return self

        # 1️⃣ Precio de la venta
        if self.precio_venta is None:
            self.precio_venta = self.vehiculo.precio

        self.estado = "confirmada"
        self.save(update_fields=["estado", "precio_venta"])

        # 2️⃣ Cuenta corriente
        cuenta, _ = CuentaCorriente.objects.get_or_create(
            venta=self,
            defaults={"cliente": self.cliente}
        )

        # 3️⃣ Deuda inicial (solo una vez)
        existe_deuda = cuenta.movimientos.filter(
            origen="venta",
            tipo="debe"
        ).exists()

        if not existe_deuda:
            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                vehiculo=self.vehiculo,
                descripcion=f"Venta vehículo {self.vehiculo}",
                tipo="debe",
                monto=self.precio_venta,
                origen="venta"
            )

            cuenta.recalcular_saldo()

        return self

    # ======================================================
    # 🔧 MÉTODO DE ADJUDICACIÓN COMPLETA (SE MANTIENE)
    # ======================================================
    def adjudicar_cliente(self, cliente):
        """
        Se llama cuando se asigna un cliente a la venta.
        Garantiza que:
        - la venta quede confirmada
        - exista Cuenta Corriente
        - exista Gestoría
        - el gasto de Gestoría se impute en la Cuenta Corriente
        """

        from cuentas.models import CuentaCorriente
        from gestoria.models import Gestoria

        # 1️⃣ Asignar cliente
        self.cliente = cliente
        self.save(update_fields=["cliente"])

        # 2️⃣ Confirmar venta (centralizado)
        self.confirmar()

        # 3️⃣ Crear / vincular Gestoría
        gestoria = Gestoria.crear_o_actualizar_desde_venta(
            venta=self,
            vehiculo=self.vehiculo,
            cliente=cliente
        )

        # 🔑 Automatización contable de gestoría
        gestoria.save()

        return self

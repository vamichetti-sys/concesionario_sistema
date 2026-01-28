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
        on_delete=models.SET_NULL,   # 🔑 CAMBIO CLAVE
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
        return f"Venta {self.id} - {self.vehiculo or 'Sin vehículo'} - {self.cliente or 'Sin cliente'}"

    # ======================================================
    # 🔒 CONFIRMACIÓN CENTRALIZADA (SE MANTIENE)
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

        # ==================================================
        # 1️⃣ ASEGURAR CUENTA CORRIENTE (SIEMPRE)
        # ⚠️ SOLO SI HAY CLIENTE VÁLIDO
        # ==================================================
        cuenta = None
        if self.cliente:
            cuenta, _ = CuentaCorriente.objects.get_or_create(
                venta=self,
                cliente=self.cliente
            )

        # ==================================================
        # 2️⃣ IMPUTAR DEUDA INICIAL (BLOQUE CONSERVADO)
        # ⚠️ DESHABILITADO: la deuda la genera el Plan de Pago
        # ==================================================
        if False and cuenta:
            existe_deuda = cuenta.movimientos.filter(
                origen="venta",
                tipo="debe"
            ).exists()

            if not existe_deuda:
                monto = self.precio_venta
                if monto is None and self.vehiculo:
                    monto = self.vehiculo.precio or 0

                MovimientoCuenta.objects.create(
                    cuenta=cuenta,
                    vehiculo=self.vehiculo,
                    descripcion=f"Venta vehículo {self.vehiculo}",
                    tipo="debe",
                    monto=monto or 0,
                    origen="venta"
                )

                cuenta.recalcular_saldo()

        # ==================================================
        # 3️⃣ CONFIRMAR VENTA (SIN BLOQUEAR LÓGICA)
        # ==================================================
        if self.precio_venta is None and self.vehiculo:
            self.precio_venta = self.vehiculo.precio

        if self.estado != "confirmada":
            self.estado = "confirmada"
            self.save(update_fields=["estado", "precio_venta"])
        else:
            self.save(update_fields=["precio_venta"])

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

        # ==================================================
        # 1️⃣ ASIGNAR CLIENTE A LA VENTA
        # ==================================================
        self.cliente = cliente
        self.save(update_fields=["cliente"])

        # ==================================================
        # 2️⃣ CREAR CUENTA CORRIENTE (OBLIGATORIO)
        # ==================================================
        cuenta, _ = CuentaCorriente.objects.get_or_create(
            venta=self,
            cliente=cliente
        )

        # ==================================================
        # 3️⃣ CONFIRMAR VENTA (NO CREA DEUDA)
        # ==================================================
        self.confirmar()

        # ==================================================
        # 4️⃣ SINCRONIZAR CLIENTE EN CUENTA CORRIENTE (SI EXISTÍA)
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

        # 🔑 Automatización contable de gestoría
        gestoria.save()

        return self

from django.db import models
from django.utils import timezone

from ventas.models import Venta
from clientes.models import Cliente
from vehiculos.models import Vehiculo
from cuentas.models import CuentaCorriente, MovimientoCuenta


class Gestoria(models.Model):

    ESTADO_CHOICES = [
        ("vigente", "Vigente"),
        ("finalizada", "Finalizada"),
    ]

    venta = models.OneToOneField(
        Venta,
        on_delete=models.CASCADE,
        related_name="gestoria",
        null=True,
        blank=True
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE
    )

    monto_transferencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    pagado = models.BooleanField(default=False)
    transferido = models.BooleanField(default=False)

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="vigente"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

    # ======================================================
    # 🗂️ CAMPOS DE FICHA DE GESTORÍA
    # ======================================================
    formulario_08 = models.BooleanField(default=False)
    titulo = models.BooleanField(default=False)
    cedula = models.BooleanField(default=False)
    informe_dominio = models.BooleanField(default=False)

    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones internas de la gestoría"
    )

    # ======================================================
    # 🔍 REPRESENTACIÓN
    # ======================================================
    def __str__(self):
        return f"Gestoría – {self.vehiculo}"

    # ======================================================
    # ✅ CLIENTE EFECTIVO
    # ======================================================
    @property
    def cliente_actual(self):
        if self.venta and self.venta.cliente:
            return self.venta.cliente
        return self.cliente

    # ======================================================
    # 🔧 SINCRONIZACIÓN DESDE VENTA
    # ======================================================
    @classmethod
    def crear_o_actualizar_desde_venta(cls, venta, vehiculo, cliente):
        gestoria, created = cls.objects.get_or_create(
            venta=venta,
            defaults={
                "vehiculo": vehiculo,
                "cliente": cliente,
                "estado": "vigente",
            }
        )

        cambios = []

        if gestoria.vehiculo_id != vehiculo.id:
            gestoria.vehiculo = vehiculo
            cambios.append("vehiculo")

        if gestoria.cliente_id != cliente.id:
            gestoria.cliente = cliente
            cambios.append("cliente")

        if gestoria.estado != "vigente":
            gestoria.estado = "vigente"
            cambios.append("estado")

        if cambios:
            gestoria.save(update_fields=cambios)

        return gestoria

    # ======================================================
    # 🧠 HELPERS EXISTENTES
    # ======================================================
    @property
    def documentacion_completa(self):
        return all([
            self.formulario_08,
            self.titulo,
            self.cedula,
            self.informe_dominio
        ])

    def finalizar(self):
        self.estado = "finalizada"
        if not self.fecha_finalizacion:
            self.fecha_finalizacion = timezone.now()
        self.save(update_fields=["estado", "fecha_finalizacion"])

    # ======================================================
    # ⚙️ AUTOMATIZACIÓN CONTABLE (SEGURA)
    # ======================================================
    def sincronizar_gasto_en_cuenta(self):
        """
        Imputa el gasto de gestoría UNA SOLA VEZ por venta.
        Si el monto cambia, NO duplica ni reimputa automáticamente.
        """

        if not self.venta:
            return

        try:
            cuenta = self.venta.cuenta_corriente
        except CuentaCorriente.DoesNotExist:
            return

        if self.monto_transferencia <= 0:
            return

        existe = MovimientoCuenta.objects.filter(
            cuenta=cuenta,
            origen='gestoria',
            vehiculo=self.vehiculo
        ).exists()

        if existe:
            return

        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            descripcion=f"Gestoría – Transferencia {self.vehiculo}",
            tipo='debe',
            monto=self.monto_transferencia,
            origen='gestoria',
            vehiculo=self.vehiculo
        )

        cuenta.recalcular_saldo()

    # ======================================================
    # 🔁 HOOK AUTOMÁTICO
    # ======================================================
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sincronizar_gasto_en_cuenta()

    # ======================================================
    # 🆕 HELPERS PARA REPORTE WEB (NO ROMPEN NADA)
    # ======================================================
    @property
    def esta_finalizada(self):
        """True si la transferencia está finalizada."""
        return self.estado == "finalizada"

    @property
    def esta_pendiente(self):
        """True si la transferencia sigue vigente."""
        return self.estado == "vigente"
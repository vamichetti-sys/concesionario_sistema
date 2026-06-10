from decimal import Decimal

from django.db import models, transaction
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
        on_delete=models.PROTECT
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    monto_transferencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    # Distribución del costo de la transferencia: cuánto paga cada parte
    pago_escribania = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        blank=True,
        verbose_name="Pago escribanía"
    )
    pago_cliente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        blank=True,
        verbose_name="Pago cliente"
    )
    pago_concesionaria = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        blank=True,
        verbose_name="Pago concesionaria"
    )

    # Check del pago de la concesionaria: al marcarse "gestionado" pasa al
    # listado del módulo Pagos Concesionario, con su fecha de pago.
    pago_concesionaria_gestionado = models.BooleanField(
        default=False,
        verbose_name="Pago concesionaria gestionado",
    )
    pago_concesionaria_fecha = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de pago concesionaria",
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

    # Vínculo al gasto (debe) que esta gestoría creó en la cuenta corriente,
    # para poder ACTUALIZARLO si cambia el monto y REVERTIRLO si se elimina.
    movimiento_transferencia = models.ForeignKey(
        "cuentas.MovimientoCuenta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Gasto de transferencia en cuenta",
    )

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
    def _movimiento_transferencia(self, cuenta):
        """
        Devuelve el MovimientoCuenta (debe) de esta gestoría. Usa el FK; si no
        está enlazado (gestorías viejas), adopta el debe de gestoría existente
        del mismo vehículo y lo deja enlazado.
        """
        mov = self.movimiento_transferencia
        if mov is not None:
            return mov
        return (
            MovimientoCuenta.objects.filter(
                cuenta=cuenta, origen="gestoria", tipo="debe", vehiculo=self.vehiculo
            )
            .order_by("id")
            .first()
        )

    def sincronizar_gasto_en_cuenta(self):
        """
        CREAR / ACTUALIZAR / BORRAR el gasto (debe) de la transferencia en la
        cuenta corriente, de forma centralizada y atómica:
          - monto > 0 y sin movimiento  → crea y enlaza el FK
          - monto > 0 y con movimiento  → actualiza el monto del existente
          - monto <= 0 y con movimiento → borra el movimiento
        Siempre recalcula el saldo. Nunca duplica.
        """
        if not self.venta_id:
            return

        try:
            cuenta = self.venta.cuenta_corriente
        except CuentaCorriente.DoesNotExist:
            return

        monto = self.monto_transferencia or Decimal("0")
        desc = f"Gestoría – Transferencia {self.vehiculo}"

        with transaction.atomic():
            mov = self._movimiento_transferencia(cuenta)
            nuevo_id = None

            if monto > 0:
                if mov is None:
                    mov = MovimientoCuenta.objects.create(
                        cuenta=cuenta,
                        descripcion=desc,
                        tipo="debe",
                        monto=monto,
                        origen="gestoria",
                        vehiculo=self.vehiculo,
                    )
                else:
                    campos = []
                    if mov.monto != monto:
                        mov.monto = monto
                        campos.append("monto")
                    if mov.descripcion != desc:
                        mov.descripcion = desc
                        campos.append("descripcion")
                    if campos:
                        mov.save(update_fields=campos)
                nuevo_id = mov.pk
            else:
                # monto 0: el gasto no corresponde → se borra si existía
                if mov is not None:
                    mov.delete()

            # Guardar la referencia SIN re-disparar save() (evita recursión)
            if self.movimiento_transferencia_id != nuevo_id:
                self.movimiento_transferencia_id = nuevo_id
                type(self).objects.filter(pk=self.pk).update(
                    movimiento_transferencia=nuevo_id
                )

            cuenta.recalcular_saldo()

    def revertir_gasto_en_cuenta(self):
        """Borra el gasto de transferencia en la cuenta y recalcula el saldo."""
        if not self.venta_id:
            return
        try:
            cuenta = self.venta.cuenta_corriente
        except CuentaCorriente.DoesNotExist:
            return
        with transaction.atomic():
            mov = self._movimiento_transferencia(cuenta)
            if mov is not None:
                mov.delete()
                self.movimiento_transferencia_id = None
                type(self).objects.filter(pk=self.pk).update(
                    movimiento_transferencia=None
                )
                cuenta.recalcular_saldo()

    # ======================================================
    # 🔁 HOOK AUTOMÁTICO
    # ======================================================
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sincronizar_gasto_en_cuenta()

    def delete(self, *args, **kwargs):
        # Al eliminar/revertir la gestoría, se revierte su gasto en la cuenta.
        self.revertir_gasto_en_cuenta()
        return super().delete(*args, **kwargs)

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
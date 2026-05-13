from django.db import models
from decimal import Decimal

from vehiculos.models import Vehiculo


class Reventa(models.Model):

    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("revertida", "Revertida"),
    ]

    vehiculo = models.OneToOneField(
        Vehiculo,
        on_delete=models.SET_NULL,
        related_name="reventa",
        null=True,
        blank=True,
    )

    # Agencia o persona a quien se revende
    agencia = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Agencia / Comprador",
    )
    contacto = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente",
    )

    precio_reventa = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    comision = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Comision o ganancia de la operacion",
    )

    observaciones = models.TextField(blank=True, null=True)

    documentacion_entregada = models.TextField(
        blank=True,
        null=True,
        verbose_name="Documentacion entregada",
        help_text="Detalle de documentacion entregada con el vehiculo",
    )

    # Si está tildado, al confirmar la reventa se crea automáticamente un
    # registro en Gestoría para gestionar la transferencia del vehículo.
    enviar_a_gestoria = models.BooleanField(
        default=False,
        verbose_name="Enviar a Gestoría al transferir",
    )

    # Cuenta corriente del revendedor
    cuenta = models.ForeignKey(
        "CuentaRevendedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reventas",
    )

    fecha_reventa = models.DateField(auto_now_add=True)
    fecha_confirmacion = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_reventa"]
        verbose_name = "Reventa"
        verbose_name_plural = "Reventas"

    def __str__(self):
        vehiculo_str = self.vehiculo or "Sin vehiculo"
        return f"Reventa {self.id} – {vehiculo_str} → {self.agencia or 'Sin asignar'}"

    def confirmar(self):
        from datetime import date
        self.estado = "confirmada"
        self.fecha_confirmacion = date.today()
        self.save()

        # Crear movimiento "debe" en la cuenta del revendedor
        if self.cuenta and self.precio_reventa and self.precio_reventa > 0:
            vehiculo_str = f"{self.vehiculo}" if self.vehiculo else "Vehiculo"
            ya_existe = MovimientoRevendedor.objects.filter(
                cuenta=self.cuenta,
                reventa=self,
                tipo="debe",
            ).exists()
            if not ya_existe:
                MovimientoRevendedor.objects.create(
                    cuenta=self.cuenta,
                    tipo="debe",
                    monto=self.precio_reventa,
                    descripcion=f"Reventa – {vehiculo_str}",
                    reventa=self,
                )

        # Si se marcó "enviar a gestoría", crear el registro de gestoría
        # para gestionar la transferencia. Se hace sin cliente porque la
        # contraparte es una agencia (CuentaRevendedor), no un Cliente.
        if self.enviar_a_gestoria and self.vehiculo:
            from gestoria.models import Gestoria
            ya_tiene = Gestoria.objects.filter(vehiculo=self.vehiculo, estado="vigente").exists()
            if not ya_tiene:
                obs = f"Reventa a {self.agencia or 'agencia sin asignar'}"
                Gestoria.objects.create(
                    vehiculo=self.vehiculo,
                    cliente=None,
                    estado="vigente",
                    observaciones=obs,
                )

    def revertir(self):
        # Eliminar movimientos asociados
        if self.cuenta:
            MovimientoRevendedor.objects.filter(reventa=self).delete()

        self.estado = "revertida"
        self.agencia = None
        self.cuenta = None
        self.save(update_fields=["estado", "agencia", "cuenta"])
        if self.vehiculo:
            self.vehiculo.estado = "stock"
            self.vehiculo.save(update_fields=["estado"])


# ============================================================
# CUENTA CORRIENTE DE REVENDEDOR
# ============================================================
class CuentaRevendedor(models.Model):
    ESTADOS = [
        ("al_dia", "Al dia"),
        ("deuda", "Con deuda"),
        ("cerrada", "Cerrada"),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Agencia / Revendedor")
    contacto = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)

    saldo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="al_dia")

    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Cuenta de revendedor"
        verbose_name_plural = "Cuentas de revendedores"

    def __str__(self):
        return f"{self.nombre} – Saldo: ${self.saldo}"

    def recalcular_saldo(self):
        from django.db.models import Sum
        debe = self.movimientos.filter(tipo="debe").aggregate(t=Sum("monto"))["t"] or Decimal("0")
        haber = self.movimientos.filter(tipo="haber").aggregate(t=Sum("monto"))["t"] or Decimal("0")
        self.saldo = debe - haber
        self.estado = "deuda" if self.saldo > 0 else "al_dia"
        self.save(update_fields=["saldo", "estado"])


class MovimientoRevendedor(models.Model):
    TIPOS = [
        ("debe", "Debe"),
        ("haber", "Haber"),
    ]

    cuenta = models.ForeignKey(
        CuentaRevendedor,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    descripcion = models.CharField(max_length=200)
    fecha = models.DateField(auto_now_add=True)
    reventa = models.ForeignKey(
        Reventa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos",
    )

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.tipo} ${self.monto} – {self.cuenta.nombre}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cuenta.recalcular_saldo()

    def delete(self, *args, **kwargs):
        cuenta = self.cuenta
        super().delete(*args, **kwargs)
        cuenta.recalcular_saldo()

from django.db import models
from django.db.models import Sum, Max
from decimal import Decimal
from datetime import date

from clientes.models import Cliente
from ventas.models import Venta
from vehiculos.models import Vehiculo


# ==========================================================
# CUENTA CORRIENTE
# ==========================================================
class CuentaCorriente(models.Model):
    ESTADOS = (
        ('al_dia', 'Al día'),
        ('deuda', 'Con deuda'),
        ('cerrada', 'Cerrada'),
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='cuentas_corrientes'
    )

    venta = models.OneToOneField(
        Venta,
        on_delete=models.PROTECT,
        related_name='cuenta_corriente'
    )

    saldo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='al_dia'
    )

    creada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente} | Venta #{self.venta.id}"

    # ======================================================
    # CÁLCULO AUTOMÁTICO DE SALDO
    # ======================================================
    def recalcular_saldo(self):
        """
        Reglas reales del negocio:
        - Crear plan de pago → genera deuda
        - Registrar pago → reduce deuda
        - saldo > 0  → deuda
        - saldo = 0  → al_dia
        """
        total_debe = self.movimientos.filter(
            tipo__in=['debe', 'deuda']
        ).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')

        total_haber = self.movimientos.filter(
            tipo__in=['haber', 'pago']
        ).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0')

        saldo = total_debe - total_haber

        if saldo > 0:
            self.saldo = saldo
            self.estado = 'deuda'
        else:
            self.saldo = Decimal('0')
            self.estado = 'al_dia'

        self.save(update_fields=['saldo', 'estado'])

    # ======================================================
    # MÉTODOS DE NEGOCIO
    # ======================================================
    def registrar_deuda(self, descripcion, monto):
        MovimientoCuenta.objects.create(
            cuenta=self,
            descripcion=descripcion,
            tipo='debe',
            monto=monto,
            origen='manual'
        )
        self.recalcular_saldo()

    def registrar_pago(self, descripcion, monto):
        MovimientoCuenta.objects.create(
            cuenta=self,
            descripcion=descripcion,
            tipo='haber',
            monto=monto,
            origen='manual'
        )
        self.recalcular_saldo()

    def cerrar(self):
        if self.saldo > 0:
            raise ValueError(
                "No se puede cerrar una cuenta con deuda."
            )
        self.estado = 'cerrada'
        self.save(update_fields=['estado'])

    # ======================================================
    # HELPERS
    # ======================================================
    @property
    def tiene_deuda(self):
        return self.estado == 'deuda' and self.saldo > 0

    @property
    def tiene_deuda_vencida(self):
        plan = getattr(self, 'plan_pago', None)
        if not plan:
            return False
        return plan.cuotas.filter(
            estado='pendiente',
            vencimiento__lt=date.today()
        ).exists()


# ==========================================================
# MOVIMIENTOS CONTABLES
# ==========================================================
class MovimientoCuenta(models.Model):

    TIPOS = (
        ('debe', 'Debe'),
        ('haber', 'Haber'),
        ('deuda', 'Deuda'),
        ('pago', 'Pago'),
    )

    ORIGENES = (
        ('manual', 'Manual'),
        ('gestoria', 'Gestoría'),
        ('permuta', 'Permuta'),
        ('ajuste', 'Ajuste'),
        ('venta', 'Venta'),
    )

    cuenta = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.CASCADE,
        related_name='movimientos'
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_cuenta'
    )

    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    origen = models.CharField(
        max_length=20,
        choices=ORIGENES,
        default='manual'
    )

    def __str__(self):
        return f"{self.get_tipo_display()} - ${self.monto}"


# ==========================================================
# PLAN DE PAGO
# ==========================================================
class PlanPago(models.Model):
    ESTADOS = (
        ('activo', 'Activo'),
        ('finalizado', 'Finalizado'),
    )

    MONEDAS = (
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
    )

    TIPOS_PLAN = (
        ('cuotas', 'Cuotas'),
        ('unico', 'Pago único'),
        ('cheques', 'Cheques'),
    )

    cuenta = models.OneToOneField(
        CuentaCorriente,
        on_delete=models.CASCADE,
        related_name='plan_pago'
    )

    descripcion = models.CharField(max_length=255)
    anticipo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cantidad_cuotas = models.PositiveIntegerField()
    monto_cuota = models.DecimalField(max_digits=14, decimal_places=2)
    fecha_inicio = models.DateField()
    monto_financiado = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    tipo_plan = models.CharField(
        max_length=20,
        choices=TIPOS_PLAN,
        default='cuotas'
    )

    interes_descripcion = models.TextField(blank=True)
    interes_mora_mensual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    moneda = models.CharField(
        max_length=3,
        choices=MONEDAS,
        default='ARS'
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='activo'
    )

    creada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Plan {self.get_tipo_plan_display()} | {self.cuenta}"

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        if es_nuevo:
            cuenta = self.cuenta

            # ✅ FIX: Siempre crear el movimiento de deuda para cada plan nuevo
            # Antes se usaba icontains='Plan de pago' y si ya existía uno viejo
            # (por ejemplo de un plan anulado), no se creaba la deuda nueva.
            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                descripcion=f'Plan de pago #{self.pk} - {self.descripcion}',
                tipo='debe',
                monto=self.monto_financiado,
                origen='venta'
            )
            cuenta.recalcular_saldo()

    def verificar_finalizacion(self):
        if not self.cuotas.filter(estado='pendiente').exists():
            self.estado = 'finalizado'
            self.save(update_fields=['estado'])
            self.cuenta.recalcular_saldo()


# ==========================================================
# CUOTAS DEL PLAN
# ==========================================================
class CuotaPlan(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
    )

    plan = models.ForeignKey(
        PlanPago,
        on_delete=models.CASCADE,
        related_name='cuotas'
    )

    numero = models.PositiveIntegerField()
    vencimiento = models.DateField()
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente'
    )

    def __str__(self):
        return f"Cuota {self.numero} - ${self.monto}"

    @property
    def esta_vencida(self):
        return self.estado == 'pendiente' and self.vencimiento < date.today()

    @property
    def total_pagado(self):
        return (
            self.pagos.aggregate(
                total=Sum('monto_aplicado')
            ).get('total') or Decimal('0')
        )

    @property
    def saldo_pendiente(self):
        return max(self.monto - self.total_pagado, Decimal('0'))

    def calcular_mora(self):
        if not self.esta_vencida:
            return Decimal('0')
        return self.saldo_pendiente * (self.plan.interes_mora_mensual / Decimal('100'))

    def marcar_pagada(self):
        if self.total_pagado >= self.monto and self.estado != 'pagada':
            self.estado = 'pagada'
            self.save(update_fields=['estado'])
            self.plan.verificar_finalizacion()


# ==========================================================
# PAGO
# ==========================================================
class Pago(models.Model):
    FORMAS_PAGO = (
        ('efectivo', 'Efectivo'),
        ('cheque', 'Cheque'),
    )

    cuenta = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.CASCADE,
        related_name='pagos'
    )

    numero_recibo = models.CharField(max_length=20, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    forma_pago = models.CharField(max_length=20, choices=FORMAS_PAGO)
    banco = models.CharField(max_length=100, blank=True)
    numero_cheque = models.CharField(max_length=100, blank=True)

    monto_total = models.DecimalField(max_digits=14, decimal_places=2)
    observaciones = models.TextField(blank=True)

    saldo_anterior = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    saldo_posterior = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Recibo {self.numero_recibo or self.id} - ${self.monto_total}"

    def save(self, *args, **kwargs):
        if not self.numero_recibo:
            year = date.today().year
            ultimo = (
                Pago.objects
                .filter(numero_recibo__startswith=f"RC-{year}")
                .aggregate(max=Max('numero_recibo'))
                .get('max')
            )

            siguiente = int(ultimo.split('-')[-1]) + 1 if ultimo else 1
            self.numero_recibo = f"RC-{year}-{str(siguiente).zfill(6)}"

        super().save(*args, **kwargs)


# ==========================================================
# APLICACIÓN DEL PAGO A CUOTAS
# ==========================================================
class PagoCuota(models.Model):
    pago = models.ForeignKey(
        Pago,
        on_delete=models.CASCADE,
        related_name="aplicaciones"
    )

    cuota = models.ForeignKey(
        CuotaPlan,
        on_delete=models.CASCADE,
        related_name="pagos"
    )

    monto_aplicado = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    def __str__(self):
        return f"Pago ${self.monto_aplicado} a {self.cuota}"

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        if not es_nuevo:
            return

        cuenta = self.cuota.plan.cuenta

        if self.cuota.plan.cantidad_cuotas == 1:
            base = "Pago único"
        else:
            base = f"Pago cuota {self.cuota.numero}"

        try:
            forma = self.pago.get_forma_pago_display()
        except Exception:
            forma = "Pago"

        obs = (
            f" – {self.pago.observaciones}"
            if getattr(self.pago, "observaciones", None)
            else ""
        )

        descripcion = f"{base} ({forma}){obs}"

        MovimientoCuenta.objects.create(
            cuenta=cuenta,
            descripcion=descripcion,
            tipo="haber",
            monto=self.monto_aplicado,
            origen="venta"
        )

        cuenta.recalcular_saldo()


# ==========================================================
# BITÁCORA DE ACCIONES
# ==========================================================
class BitacoraCuenta(models.Model):
    cuenta = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.CASCADE,
        related_name='bitacora'
    )

    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=100)
    detalle = models.TextField(blank=True)

    def __str__(self):
        return f"{self.fecha} - {self.accion}"


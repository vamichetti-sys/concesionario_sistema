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
        on_delete=models.SET_NULL,
        related_name='cuenta_corriente',
        null=True,
        blank=True,
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

    observaciones = models.TextField(
        blank=True,
        default="",
        help_text="Notas internas sobre el cliente / cuenta",
    )

    creada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente} | Venta #{self.venta.id}"

    # ======================================================
    # CÁLCULO AUTOMÁTICO DE SALDO
    # ======================================================
    def recalcular_saldo(self):
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
        else:
            self.saldo = Decimal('0')

        # El estado depende de la deuda TOTAL real
        # (plan de pago + gestoría + gastos de ingreso pendientes)
        if self.estado != 'cerrada':
            if self.deuda_total_real > 0:
                self.estado = 'deuda'
            else:
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
    def plan_pago(self):
        """
        Compatibilidad: devuelve el primer plan de la cuenta (o None).
        El sistema ahora admite VARIOS planes por cuenta (self.planes);
        esta propiedad mantiene andando el código/visual que asume uno solo.
        """
        return self.planes.order_by('id').first()

    @property
    def planes_activos(self):
        return self.planes.order_by('id')

    @property
    def tiene_deuda_vencida(self):
        return any(
            plan.cuotas.filter(
                estado='pendiente',
                vencimiento__lt=date.today()
            ).exists()
            for plan in self.planes.all()
        )

    def _vehiculo_para_gastos(self):
        """Devuelve el primer vehículo de permuta vinculado (compatibilidad)."""
        return self._vehiculos_para_gastos().first()

    def _vehiculos_para_gastos(self):
        """
        Devuelve TODOS los vehículos de permuta vinculados a la cuenta.
        Los gastos del vehículo vendido los paga la concesionaria, no el cliente.
        """
        from vehiculos.models import Vehiculo
        return (
            Vehiculo.objects
            .filter(
                movimientos_cuenta__cuenta=self,
                movimientos_cuenta__origen="permuta"
            )
            .distinct()
        )

    @property
    def deuda_total_inicial(self):
        """
        Deuda total contraída (sin descontar pagos):
        plan total + gestoría debe + gastos de ingreso totales
        """
        from django.db.models import Sum
        total = Decimal("0")

        # Total de TODOS los planes de pago (con interés) - incluye finalizados
        planes = [p for p in self.planes.all() if p.pk]
        if planes:
            for plan in planes:
                for cuota in plan.cuotas.all():
                    total += cuota.monto

            # Gastos extra / ajustes manuales contraídos (con plan) - una sola vez
            man_debe = (
                self.movimientos.filter(origen__in=["manual", "ajuste"], tipo__in=["debe", "deuda"])
                .aggregate(t=Sum("monto"))["t"] or Decimal("0")
            )
            total += man_debe

        # Gestoría debe (deuda original)
        gest_debe = (
            self.movimientos.filter(origen="gestoria", tipo="debe")
            .aggregate(t=Sum("monto"))["t"] or Decimal("0")
        )
        total += gest_debe

        # Gastos de ingreso totales (suma de todos los vehículos vinculados)
        for vehiculo in self._vehiculos_para_gastos():
            try:
                ficha = vehiculo.ficha
                for _, monto in ficha.mapa_gastos_ingreso().items():
                    if monto:
                        total += Decimal(monto)
            except Exception:
                pass

        return total

    @property
    def total_pagado_real(self):
        """Total efectivamente pagado = deuda inicial - deuda actual."""
        return self.deuda_total_inicial - self.deuda_total_real

    @property
    def deuda_total_real(self):
        """
        Saldo pendiente actual = saldo cuotas del plan + gestoría pendiente + gastos pendientes
        """
        from django.db.models import Sum
        total = Decimal("0")

        # Saldo de TODOS los planes (si hay, usar saldos de cuotas)
        # Con plan: self.saldo se ignora — se suma gestoría aparte.
        # Sin plan: self.saldo YA incluye gestoría (es debe-haber de todos los movimientos),
        #           así que NO volver a sumarla.
        planes = [p for p in self.planes.all() if p.pk]
        if planes:
            for plan in planes:
                for cuota in plan.cuotas.all():
                    total += cuota.saldo_pendiente

            gest_debe = (
                self.movimientos.filter(origen="gestoria", tipo="debe")
                .aggregate(t=Sum("monto"))["t"] or Decimal("0")
            )
            gest_haber = (
                self.movimientos.filter(origen="gestoria", tipo="haber")
                .aggregate(t=Sum("monto"))["t"] or Decimal("0")
            )
            gest_pendiente = gest_debe - gest_haber
            if gest_pendiente > 0:
                total += gest_pendiente

            # Gastos extra / ajustes manuales (no van por el plan ni gestoría)
            man_debe = (
                self.movimientos.filter(origen__in=["manual", "ajuste"], tipo__in=["debe", "deuda"])
                .aggregate(t=Sum("monto"))["t"] or Decimal("0")
            )
            man_haber = (
                self.movimientos.filter(origen__in=["manual", "ajuste"], tipo__in=["haber", "pago"])
                .aggregate(t=Sum("monto"))["t"] or Decimal("0")
            )
            man_pendiente = man_debe - man_haber
            if man_pendiente > 0:
                total += man_pendiente
        else:
            total += max(self.saldo or Decimal("0"), Decimal("0"))

        # Gastos de ingreso pendientes (suma de todos los vehículos vinculados)
        for vehiculo in self._vehiculos_para_gastos():
            try:
                ficha = vehiculo.ficha
                total += ficha.saldo_total_gastos()
            except Exception:
                pass

        return total


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

    pago = models.ForeignKey(
        "Pago",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_creados",
        help_text="Pago que originó este movimiento (si aplica)",
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
        ('cuotas', 'Cuotas en pesos'),
        ('unico', 'Pago único'),
        ('cheques', 'Cheques'),
    )

    cuenta = models.ForeignKey(
        CuentaCorriente,
        on_delete=models.CASCADE,
        related_name='planes'
    )

    descripcion = models.CharField(max_length=255)
    anticipo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cantidad_cuotas = models.PositiveIntegerField()
    monto_cuota = models.DecimalField(max_digits=14, decimal_places=2)
    fecha_inicio = models.DateField()
    monto_financiado = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Monto base sobre el cual se cuotifica. Si está en 0, se usa el cálculo
    # automático (monto_financiado - anticipo). Si se carga un valor > 0,
    # se usa ese número directo como base de las cuotas.
    cuotificacion = models.DecimalField(
        "Cuotificación (monto a cuotificar)",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Monto sobre el cual se calculan las cuotas. Si queda en 0 se usa (financiado − anticipo).",
    )

    # Importe de una cuota adicional al final del plan (opcional).
    cuota_extra = models.DecimalField(
        "Cuota extra",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Si se carga, se agrega una cuota adicional con este importe al final del plan.",
    )

    tipo_plan = models.CharField(
        max_length=20,
        choices=TIPOS_PLAN,
        default='cuotas'
    )

    # 🔹 Interés de financiación (sobre el total, ej: 40%)
    interes_financiacion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        blank=True,
        help_text="Porcentaje de interés aplicado al monto financiado. Ej: 40 = 40%"
    )

    # 🔹 Interés por mora de cuota (mensual) — opcional
    interes_mora_mensual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        blank=True,
        help_text="Porcentaje de mora mensual por cuota vencida (opcional). Ej: 4 = 4%"
    )

    interes_descripcion = models.TextField(blank=True)

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

    # ======================================================
    # PROPIEDAD: total con interés de financiación
    # ======================================================
    @property
    def base_cuotificacion(self):
        """Monto base sobre el que se cuotifica antes del interés."""
        if self.cuotificacion and self.cuotificacion > 0:
            return self.cuotificacion
        base = (self.monto_financiado or Decimal('0')) - (self.anticipo or Decimal('0'))
        return base if base > 0 else Decimal('0')

    @property
    def total_con_interes(self):
        """
        Base a cuotificar + interés + cuota extra (si tiene).
        Determina el "debe" del plan en la cuenta corriente.
        """
        base = self.base_cuotificacion
        if self.interes_financiacion and self.interes_financiacion > 0:
            factor = Decimal('1') + (self.interes_financiacion / Decimal('100'))
            total = base * factor
        else:
            total = base
        if self.cuota_extra and self.cuota_extra > 0:
            total += self.cuota_extra
        return total.quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        if es_nuevo:
            cuenta = self.cuenta

            # La deuda se genera por el total con interés de financiación
            monto_deuda = self.total_con_interes

            MovimientoCuenta.objects.create(
                cuenta=cuenta,
                descripcion=f'Plan de pago #{self.pk} - {self.descripcion}',
                tipo='debe',
                monto=monto_deuda,
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
        return self.estado == 'pendiente' and self.vencimiento < date.today() and self.saldo_pendiente > 0

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
        ('transferencia', 'Transferencia'),  # ✅ agregado
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
    fecha_cobro_cheque = models.DateField(null=True, blank=True)
    titular_cheque = models.CharField(max_length=255, blank=True)
    cheque_vinculado = models.ForeignKey(
        "cheques.Cheque",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_origen",
    )

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
            origen="venta",
            pago=self.pago,
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

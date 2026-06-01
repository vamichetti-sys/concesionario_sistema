from datetime import date

from django.db import models
from django.contrib.auth.models import User


class CuentaInterna(models.Model):
    nombre = models.CharField('Nombre / Persona', max_length=255)
    cargo = models.CharField('Cargo / Concepto', max_length=255)
    telefono = models.CharField('Teléfono', max_length=50, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    saldo = models.DecimalField('Saldo', max_digits=12, decimal_places=2, default=0)
    
    activa = models.BooleanField('Activa', default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Cuenta Interna'
        verbose_name_plural = 'Cuentas Internas'

    def __str__(self):
        return f"{self.nombre} - {self.cargo}"

    def recalcular_saldo(self):
        from django.db.models import Sum
        debe = self.movimientos.filter(tipo='debe').aggregate(Sum('monto'))['monto__sum'] or 0
        haber = self.movimientos.filter(tipo='haber').aggregate(Sum('monto'))['monto__sum'] or 0
        self.saldo = debe - haber
        self.save(update_fields=['saldo'])


class MovimientoInterno(models.Model):
    TIPO_CHOICES = [
        ('debe', 'Debe (Cargo)'),
        ('haber', 'Haber (Pago)'),
    ]
    
    cuenta = models.ForeignKey(CuentaInterna, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField('Monto', max_digits=12, decimal_places=2)
    concepto = models.CharField('Concepto', max_length=255)
    fecha = models.DateField('Fecha')
    observaciones = models.TextField('Observaciones', blank=True)
    
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Movimiento'
        verbose_name_plural = 'Movimientos'

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.monto} - {self.concepto}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cuenta.recalcular_saldo()

    def delete(self, *args, **kwargs):
        cuenta = self.cuenta
        super().delete(*args, **kwargs)
        cuenta.recalcular_saldo()


# ==========================================================
# ALQUILERES
# ==========================================================
class Alquiler(models.Model):
    nombre = models.CharField('Nombre / Inmueble', max_length=255,
                              help_text='Ej: Local centro, Galpón, Depósito anexo')
    direccion = models.CharField('Dirección', max_length=255, blank=True)
    arrendatario = models.CharField('Arrendatario / Inquilino', max_length=255, blank=True,
                                    help_text='Quién alquila y paga el alquiler')
    telefono = models.CharField('Teléfono', max_length=50, blank=True)

    monto_mensual = models.DecimalField('Monto mensual', max_digits=12, decimal_places=2, default=0,
                                        help_text='Monto inicial. Si hay aumento programado, se ajusta solo.')
    dia_pago = models.PositiveSmallIntegerField('Día de pago', null=True, blank=True,
                                                help_text='Día del mes en que se paga (1-31)')

    # Aumento programado del alquiler (ej: cada 3 meses sube 10%)
    aumento_porcentaje = models.DecimalField(
        'Aumento (%)', max_digits=6, decimal_places=2, default=0, blank=True,
        help_text='Porcentaje de aumento. Ej: 10 = 10%',
    )
    aumento_cada_meses = models.PositiveSmallIntegerField(
        'Aumenta cada (meses)', null=True, blank=True,
        help_text='Cada cuántos meses aumenta. Ej: 3 = trimestral. Vacío = sin aumento.',
    )

    fecha_inicio = models.DateField('Inicio de contrato', null=True, blank=True)
    fecha_fin = models.DateField('Fin de contrato', null=True, blank=True)

    contrato = models.FileField('Contrato escaneado', upload_to='alquileres/contratos/',
                                null=True, blank=True,
                                help_text='PDF o imagen del contrato firmado')

    observaciones = models.TextField('Observaciones', blank=True)
    activo = models.BooleanField('Activo', default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Alquiler'
        verbose_name_plural = 'Alquileres'

    def __str__(self):
        return self.nombre

    @property
    def total_pagado(self):
        from django.db.models import Sum
        return self.pagos.aggregate(t=Sum('monto'))['t'] or 0

    @property
    def ultimo_pago(self):
        return self.pagos.order_by('-fecha', '-id').first()

    @property
    def pagado_mes_actual(self):
        """True si ya hay un pago registrado en el mes/año en curso."""
        hoy = date.today()
        return self.pagos.filter(fecha__year=hoy.year, fecha__month=hoy.month).exists()

    def cronograma(self):
        """
        Devuelve una fila por cada mes del contrato (de fecha_inicio a
        fecha_fin) con el monto a cobrar y el pago asociado (si existe).
        """
        if not (self.fecha_inicio and self.fecha_fin):
            return []
        from decimal import Decimal
        MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        pagos = {}
        for p in self.pagos.all():
            if p.periodo_anio and p.periodo_mes:
                pagos[(p.periodo_anio, p.periodo_mes)] = p

        base = self.monto_mensual or Decimal("0")
        pct = self.aumento_porcentaje or Decimal("0")
        cada = self.aumento_cada_meses or 0
        factor = Decimal("1") + (Decimal(pct) / Decimal("100"))

        filas = []
        y, m = self.fecha_inicio.year, self.fecha_inicio.month
        endy, endm = self.fecha_fin.year, self.fecha_fin.month
        idx = 0
        guard = 0
        while (y, m) <= (endy, endm) and guard < 600:
            guard += 1
            # Monto con aumento programado: cada `cada` meses sube `pct`%.
            if cada and cada > 0 and pct:
                monto = (base * (factor ** (idx // cada))).quantize(Decimal("0.01"))
            else:
                monto = base
            pago = pagos.get((y, m))
            filas.append({
                "anio": y, "mes": m,
                "label": f"{MESES[m]} {y}",
                "monto": monto,
                "pago": pago,
                "cobrado": pago is not None,
            })
            idx += 1
            m += 1
            if m > 12:
                m = 1
                y += 1
        return filas

    @property
    def total_a_cobrar_contrato(self):
        """Monto total del contrato = meses x monto mensual."""
        filas = self.cronograma()
        from decimal import Decimal
        return sum((f["monto"] or Decimal("0")) for f in filas)

    @property
    def proximo_vencimiento(self):
        """Próxima fecha de pago estimada según el día de pago."""
        if not self.dia_pago:
            return None
        hoy = date.today()
        import calendar
        last_day = calendar.monthrange(hoy.year, hoy.month)[1]
        dia = min(self.dia_pago, last_day)
        venc = date(hoy.year, hoy.month, dia)
        if venc < hoy:
            # mes siguiente
            year = hoy.year + (1 if hoy.month == 12 else 0)
            month = 1 if hoy.month == 12 else hoy.month + 1
            last_day = calendar.monthrange(year, month)[1]
            venc = date(year, month, min(self.dia_pago, last_day))
        return venc


class PagoAlquiler(models.Model):
    FORMA_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ]

    alquiler = models.ForeignKey(Alquiler, on_delete=models.CASCADE, related_name='pagos')
    fecha = models.DateField('Fecha de cobro')
    periodo_mes = models.PositiveSmallIntegerField('Mes del período', null=True, blank=True)
    periodo_anio = models.PositiveIntegerField('Año del período', null=True, blank=True)
    monto = models.DecimalField('Monto', max_digits=12, decimal_places=2)
    forma_pago = models.CharField('Forma de pago', max_length=20, choices=FORMA_CHOICES,
                                  default='transferencia')
    observaciones = models.TextField('Observaciones', blank=True)

    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Pago de alquiler'
        verbose_name_plural = 'Pagos de alquiler'

    @property
    def periodo_label(self):
        if self.periodo_mes and self.periodo_anio:
            MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            return f"{MESES[self.periodo_mes]} {self.periodo_anio}"
        return ""

    def __str__(self):
        return f"{self.alquiler.nombre} - ${self.monto} ({self.periodo_label or self.fecha})"
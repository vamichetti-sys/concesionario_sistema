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
    propietario = models.CharField('Propietario', max_length=255, blank=True)
    telefono = models.CharField('Teléfono', max_length=50, blank=True)

    monto_mensual = models.DecimalField('Monto mensual', max_digits=12, decimal_places=2, default=0)
    dia_pago = models.PositiveSmallIntegerField('Día de pago', null=True, blank=True,
                                                help_text='Día del mes en que se paga (1-31)')

    fecha_inicio = models.DateField('Inicio de contrato', null=True, blank=True)
    fecha_fin = models.DateField('Fin de contrato', null=True, blank=True)

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
    fecha = models.DateField('Fecha de pago')
    periodo = models.CharField('Período', max_length=50, blank=True,
                               help_text='Ej: Junio 2026')
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

    def __str__(self):
        return f"{self.alquiler.nombre} - ${self.monto} ({self.periodo or self.fecha})"
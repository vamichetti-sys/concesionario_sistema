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
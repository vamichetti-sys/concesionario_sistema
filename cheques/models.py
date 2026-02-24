from django.db import models
from django.contrib.auth.models import User


class Cheque(models.Model):
    TIPO_CHOICES = [
        ('recibido', 'Recibido'),
        ('emitido', 'Emitido'),
    ]
    
    ESTADO_CHOICES = [
        ('cartera', 'En cartera'),
        ('depositado', 'Depositado'),
        ('cobrado', 'Cobrado'),
        ('entregado', 'Entregado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]
    
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    numero = models.CharField('Número de cheque', max_length=50)
    banco = models.CharField('Banco', max_length=100)
    
    titular = models.CharField('Titular', max_length=255)
    cuit_titular = models.CharField('CUIT Titular', max_length=20, blank=True)
    
    monto = models.DecimalField('Monto', max_digits=12, decimal_places=2)
    fecha_emision = models.DateField('Fecha de emisión')
    fecha_cobro = models.DateField('Fecha de cobro')
    
    estado = models.CharField('Estado', max_length=20, choices=ESTADO_CHOICES, default='cartera')
    
    # A quién se recibió o entregó
    origen_destino = models.CharField('Origen/Destino', max_length=255, help_text='De quién se recibió o a quién se entregó')
    concepto = models.CharField('Concepto', max_length=255, blank=True)
    
    observaciones = models.TextField('Observaciones', blank=True)
    
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_cobro']
        verbose_name = 'Cheque'
        verbose_name_plural = 'Cheques'

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.numero} - ${self.monto}"

    @property
    def esta_vencido(self):
        from datetime import date
        return self.fecha_cobro < date.today() and self.estado == 'cartera'
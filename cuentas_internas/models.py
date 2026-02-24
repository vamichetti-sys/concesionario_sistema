from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta


class Cheque(models.Model):
    ESTADO_CHOICES = [
        ('a_depositar', 'A Depositar'),
        ('depositado', 'Depositado'),
        ('endosado', 'Endosado'),
        ('rechazado', 'Rechazado'),
    ]
    
    # Datos de ingreso
    fecha_ingreso = models.DateField('Fecha de ingreso', default=date.today)
    cliente = models.CharField('Cliente', max_length=255)
    nro_factura = models.CharField('Nro de Factura', max_length=50, blank=True)
    
    # Datos del cheque
    banco_emision = models.CharField('Banco de emisión', max_length=100)
    numero_cheque = models.CharField('Número de cheque', max_length=50)
    titular_cheque = models.CharField('Titular del cheque', max_length=255)
    monto = models.DecimalField('Monto', max_digits=12, decimal_places=2)
    fecha_deposito = models.DateField('Fecha de depósito/cobro')
    
    # Estado
    estado = models.CharField('Estado', max_length=20, choices=ESTADO_CHOICES, default='a_depositar')
    
    # Si fue depositado
    depositado_en = models.CharField('Depositado en', max_length=255, blank=True)
    
    # Si fue endosado
    fecha_endoso = models.DateField('Fecha de endoso', null=True, blank=True)
    destinatario_endoso = models.CharField('Destinatario del endoso', max_length=255, blank=True)
    
    # Observaciones
    observaciones = models.TextField('Observaciones', blank=True)
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_deposito', '-monto']
        verbose_name = 'Cheque'
        verbose_name_plural = 'Cheques'

    def __str__(self):
        return f"#{self.numero_cheque} - {self.titular_cheque} - ${self.monto}"

    @property
    def dias_para_deposito(self):
        """Días que faltan para la fecha de depósito"""
        if self.estado != 'a_depositar':
            return None
        delta = (self.fecha_deposito - date.today()).days
        return delta

    @property
    def rango_vencimiento(self):
        """Categoría de vencimiento para el resumen"""
        dias = self.dias_para_deposito
        if dias is None:
            return None
        if dias < 0:
            return 'vencido'
        elif dias == 0:
            return 'hoy'
        elif dias <= 7:
            return '1_7'
        elif dias <= 15:
            return '8_15'
        elif dias <= 30:
            return '16_30'
        elif dias <= 60:
            return '31_60'
        else:
            return 'mas_60'

    @classmethod
    def resumen_por_vencimiento(cls):
        """Genera resumen de cheques a depositar por rango de fechas"""
        hoy = date.today()
        cheques = cls.objects.filter(estado='a_depositar')
        
        rangos = {
            'vencido': {'monto': 0, 'cantidad': 0, 'desde': None, 'hasta': hoy - timedelta(days=1)},
            'hoy': {'monto': 0, 'cantidad': 0, 'fecha': hoy},
            '1_7': {'monto': 0, 'cantidad': 0, 'desde': hoy + timedelta(days=1), 'hasta': hoy + timedelta(days=7)},
            '8_15': {'monto': 0, 'cantidad': 0, 'desde': hoy + timedelta(days=8), 'hasta': hoy + timedelta(days=15)},
            '16_30': {'monto': 0, 'cantidad': 0, 'desde': hoy + timedelta(days=16), 'hasta': hoy + timedelta(days=30)},
            '31_60': {'monto': 0, 'cantidad': 0, 'desde': hoy + timedelta(days=31), 'hasta': hoy + timedelta(days=60)},
            'mas_60': {'monto': 0, 'cantidad': 0, 'desde': hoy + timedelta(days=61), 'hasta': None},
        }
        
        for cheque in cheques:
            rango = cheque.rango_vencimiento
            if rango:
                rangos[rango]['monto'] += cheque.monto
                rangos[rango]['cantidad'] += 1
        
        # Total
        total_monto = sum(r['monto'] for r in rangos.values())
        total_cantidad = sum(r['cantidad'] for r in rangos.values())
        
        return rangos, total_monto, total_cantidad
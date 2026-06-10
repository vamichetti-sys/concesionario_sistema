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

    # Vínculo al cobro que este cheque saldó (cuenta corriente). Sirve para
    # poder REVERTIR el cobro si el cheque se rechaza. Es 1 cheque ↔ 1 Pago.
    # Los cheques de un plan de pago tipo cheques quedan con cobro=None
    # (todavía no generaron cobro real).
    cobro = models.ForeignKey(
        "cuentas.Pago",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cheques_cobro",
        verbose_name="Cobro que saldó",
    )

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
        if self.estado != 'a_depositar':
            return None
        delta = (self.fecha_deposito - date.today()).days
        return delta

    @classmethod
    def resumen_por_vencimiento(cls):
        hoy = date.today()
        cheques = cls.objects.filter(estado='a_depositar')
        
        rangos = {
            'vencido': {'monto': 0, 'cantidad': 0},
            'hoy': {'monto': 0, 'cantidad': 0},
            'd1_7': {'monto': 0, 'cantidad': 0},
            'd8_15': {'monto': 0, 'cantidad': 0},
            'd16_30': {'monto': 0, 'cantidad': 0},
            'd31_60': {'monto': 0, 'cantidad': 0},
            'mas60': {'monto': 0, 'cantidad': 0},
        }
        
        for cheque in cheques:
            dias = (cheque.fecha_deposito - hoy).days
            if dias < 0:
                rango = 'vencido'
            elif dias == 0:
                rango = 'hoy'
            elif dias <= 7:
                rango = 'd1_7'
            elif dias <= 15:
                rango = 'd8_15'
            elif dias <= 30:
                rango = 'd16_30'
            elif dias <= 60:
                rango = 'd31_60'
            else:
                rango = 'mas60'
            
            rangos[rango]['monto'] += cheque.monto
            rangos[rango]['cantidad'] += 1
        
        total_monto = sum(r['monto'] for r in rangos.values())
        total_cantidad = sum(r['cantidad'] for r in rangos.values())

        return rangos, total_monto, total_cantidad

    @classmethod
    def crear_desde_cobro(cls, *, cliente, monto, fecha_deposito=None,
                          banco_emision="", numero_cheque="", titular_cheque="",
                          nro_factura="", creado_por=None, observaciones="",
                          cobro=None):
        """
        Crea un cheque 'a depositar' a partir de un cobro (cuenta corriente
        o reventa) pagado con cheque. Queda disponible automáticamente en
        Gestión de Cheques. `cobro` es el cuentas.Pago que este cheque saldó
        (para poder revertirlo si se rechaza).
        """
        return cls.objects.create(
            cliente=(cliente or "").strip() or "Sin nombre",
            nro_factura=nro_factura or "",
            banco_emision=banco_emision or "",
            numero_cheque=numero_cheque or "",
            titular_cheque=(titular_cheque or cliente or "").strip(),
            monto=monto,
            fecha_deposito=fecha_deposito or date.today(),
            estado="a_depositar",
            creado_por=creado_por,
            observaciones=observaciones or "",
            cobro=cobro,
        )

    def registrar_movimiento(self, estado_nuevo, usuario=None, destinatario="", detalle=""):
        """Deja asentado en el historial un cambio de estado del cheque."""
        return MovimientoCheque.objects.create(
            cheque=self,
            estado_nuevo=estado_nuevo,
            destinatario=destinatario or "",
            detalle=detalle or "",
            usuario=usuario if (usuario and usuario.is_authenticated) else None,
        )


# ==========================================================
# HISTORIAL / MOVIMIENTOS DEL CHEQUE
# ==========================================================
class MovimientoCheque(models.Model):
    """
    Un registro por cada cambio de estado del cheque (depósito, endoso,
    rechazo, etc.). Permite ver el ciclo de vida completo, no solo el
    estado actual.
    """
    cheque = models.ForeignKey(
        Cheque,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    estado_nuevo = models.CharField(max_length=20, choices=Cheque.ESTADO_CHOICES)
    destinatario = models.CharField('Destinatario (endoso)', max_length=255, blank=True)
    detalle = models.CharField('Detalle', max_length=255, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Movimiento de cheque'
        verbose_name_plural = 'Movimientos de cheques'

    def __str__(self):
        return f"{self.cheque} → {self.get_estado_nuevo_display()} ({self.fecha:%d/%m/%Y})"
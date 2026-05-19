from django.db import models
from django.contrib.auth.models import User
from vehiculos.models import Vehiculo
from clientes.models import Cliente


class Presupuesto(models.Model):
    numero = models.PositiveIntegerField('Número', unique=True)

    # Cliente (puede ser un lead que todavía no es cliente)
    nombre_cliente = models.CharField('Nombre del cliente', max_length=255)
    telefono_cliente = models.CharField('Teléfono', max_length=50, blank=True)
    email_cliente = models.EmailField('Email', blank=True)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='presupuestos'
    )

    # Vehículo del stock (opcional: si el presupuesto es por un 0km
    # u otro auto que todavía no está en stock, se completan los
    # campos manuales de abajo).
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='presupuestos',
    )

    # Datos manuales del vehículo (para 0km o autos fuera de stock)
    es_0km = models.BooleanField('Es 0km', default=False)
    vehiculo_descripcion = models.CharField(
        'Descripción del vehículo',
        max_length=255,
        blank=True,
        help_text='Marca / Modelo / Versión cuando el vehículo no está en stock.',
    )
    vehiculo_anio = models.CharField('Año', max_length=10, blank=True)
    vehiculo_color = models.CharField('Color', max_length=80, blank=True)

    # Precios
    precio_lista = models.DecimalField('Precio de lista', max_digits=12, decimal_places=2)
    descuento_porcentaje = models.DecimalField(
        'Descuento %', max_digits=5, decimal_places=2, default=0
    )
    precio_final = models.DecimalField('Precio final', max_digits=12, decimal_places=2)

    MONEDA_CHOICES = [('ARS', 'Pesos'), ('USD', 'Dólares')]
    moneda = models.CharField('Moneda', max_length=3, choices=MONEDA_CHOICES, default='ARS')

    # Forma de pago
    FORMA_PAGO_CHOICES = [
        ('contado', 'Contado'),
        ('financiado', 'Financiado'),
    ]
    forma_pago = models.CharField('Forma de pago', max_length=20, choices=FORMA_PAGO_CHOICES, default='contado')

    # Si es financiado
    anticipo = models.DecimalField('Anticipo', max_digits=12, decimal_places=2, default=0)
    cantidad_cuotas = models.PositiveIntegerField('Cantidad de cuotas', default=1)
    monto_cuota = models.DecimalField('Monto cuota', max_digits=12, decimal_places=2, default=0)
    interes_descripcion = models.CharField('Interés / Descripción', max_length=255, blank=True)

    # Toma de usado
    toma_usado = models.BooleanField('¿Toma usado?', default=False)
    usado_descripcion = models.CharField('Usado (descripción)', max_length=255, blank=True)
    usado_valor = models.DecimalField('Valor del usado', max_digits=12, decimal_places=2, default=0)

    # Gastos adicionales
    gastos_transferencia = models.DecimalField('Gastos transferencia', max_digits=12, decimal_places=2, default=0)
    otros_gastos = models.DecimalField('Otros gastos', max_digits=12, decimal_places=2, default=0)
    gastos_descripcion = models.CharField('Detalle otros gastos', max_length=255, blank=True)

    # Observaciones
    observaciones = models.TextField('Observaciones', blank=True)
    validez_dias = models.PositiveIntegerField('Validez (días)', default=7)

    # Estado
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido'),
    ]
    estado = models.CharField('Estado', max_length=20, choices=ESTADO_CHOICES, default='borrador')

    # Vendedor
    vendedor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='presupuestos'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField('Fecha de envío', null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Presupuesto'
        verbose_name_plural = 'Presupuestos'

    def __str__(self):
        return f"Presupuesto #{self.numero} — {self.nombre_cliente}"

    @property
    def vehiculo_display(self):
        """Texto descriptivo del vehículo, tanto si es del stock como si es 0km."""
        if self.vehiculo:
            return f"{self.vehiculo.marca} {self.vehiculo.modelo}".strip()
        return self.vehiculo_descripcion or "Vehículo sin especificar"

    @property
    def vehiculo_subdetalle(self):
        """Línea secundaria: año + dominio para stock, año + color para 0km."""
        if self.vehiculo:
            partes = []
            if self.vehiculo.anio:
                partes.append(str(self.vehiculo.anio))
            if self.vehiculo.dominio:
                partes.append(self.vehiculo.dominio)
            return " · ".join(partes)
        partes = []
        if self.vehiculo_anio:
            partes.append(self.vehiculo_anio)
        if self.vehiculo_color:
            partes.append(self.vehiculo_color)
        if self.es_0km:
            partes.append("0 km")
        return " · ".join(partes)

    @property
    def total_a_pagar(self):
        """Precio final + gastos - usado"""
        total = self.precio_final + self.gastos_transferencia + self.otros_gastos
        if self.toma_usado:
            total -= self.usado_valor
        return total

    @property
    def saldo_a_financiar(self):
        if self.forma_pago == 'financiado':
            return self.total_a_pagar - self.anticipo
        return 0
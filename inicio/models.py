from django.db import models

class Vehiculo(models.Model):
    ESTADOS = [
        ('stock', 'En stock'),
        ('vendido', 'Vendido'),
    ]

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    dominio = models.CharField(max_length=10, unique=True)
    anio = models.PositiveIntegerField()
    kilometros = models.PositiveIntegerField(null=True, blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='stock')

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.dominio})"

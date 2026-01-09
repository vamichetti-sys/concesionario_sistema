from django.db import models


class Cliente(models.Model):

    CUMPLIMIENTO_CHOICES = [
        ('verde', 'Cumple en tiempo y forma'),
        ('amarillo', 'Atrasos moderados'),
        ('rojo', 'Incumplimiento'),
    ]

    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dni_cuit = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)

    fecha_alta = models.DateField(auto_now_add=True)

    # 👉 NUEVO: estado lógico del cliente (NO se borra nunca)
    activo = models.BooleanField(default=True)

    # Resultado del comportamiento de pago
    cumplimiento_pago = models.CharField(
        max_length=10,
        choices=CUMPLIMIENTO_CHOICES,
        default='verde'
    )

    def __str__(self):
        estado = "Activo" if self.activo else "Inactivo"
        return f"{self.nombre_completo} ({estado})"


class ReglaComercial(models.Model):

    COLOR_CHOICES = [
        ('verde', 'Cliente cumplidor'),
        ('amarillo', 'Cliente con atrasos'),
        ('rojo', 'Cliente incumplidor'),
    ]

    color_cliente = models.CharField(
        max_length=10,
        choices=COLOR_CHOICES,
        unique=True
    )

    permite_financiacion = models.BooleanField(default=True)

    anticipo_minimo_porcentaje = models.PositiveIntegerField(
        help_text='Porcentaje mínimo de anticipo requerido'
    )

    max_cuotas = models.PositiveIntegerField(
        help_text='Cantidad máxima de cuotas permitidas'
    )

    acepta_cheques = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Regla comercial - {self.get_color_cliente_display()}"

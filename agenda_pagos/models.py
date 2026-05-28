from django.db import models
from django.contrib.auth.models import User

from gastos_mensuales.models import CategoriaGasto


class PagoFuturo(models.Model):
    """
    Pago futuro programado en la Agenda de Pagos (alquiler, impuestos,
    celular, sueldos, etc.). Al marcarse como pagado, se crea
    automáticamente el registro en el módulo destino:
    - Control de Gastos → si es un gasto de la concesionaria.
    - Gastos Personales → si es un gasto personal del usuario que paga.
    """

    DESTINO_CONTROL_GASTOS = "control_gastos"
    DESTINO_GASTOS_PERSONALES = "gastos_personales"
    DESTINO_CHOICES = [
        (DESTINO_CONTROL_GASTOS, "Control de Gastos"),
        (DESTINO_GASTOS_PERSONALES, "Gastos Personales"),
    ]

    FORMA_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("cheque", "Cheque"),
        ("otro", "Otro"),
    ]

    descripcion = models.CharField("Descripción", max_length=200)
    monto = models.DecimalField("Monto", max_digits=14, decimal_places=2)
    fecha_vencimiento = models.DateField("Fecha de vencimiento")

    categoria = models.ForeignKey(
        CategoriaGasto, on_delete=models.PROTECT, related_name="pagos_futuros",
        null=True, blank=True,
        help_text="Tipo de pago (alquiler, sueldos, celular, etc.)",
    )

    destino = models.CharField(
        "Destino al marcar pagado", max_length=20, choices=DESTINO_CHOICES,
        default=DESTINO_CONTROL_GASTOS,
        help_text="Control de Gastos = gasto de la concesionaria · Gastos Personales = gasto del usuario que paga.",
    )

    forma_pago = models.CharField(
        "Forma de pago", max_length=20, choices=FORMA_PAGO_CHOICES, blank=True,
        help_text="Cargado al momento de marcar como pagado.",
    )

    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    pagado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pagos_futuros_pagados",
        help_text="Usuario que marcó el pago como pagado.",
    )

    observaciones = models.TextField(blank=True)

    # Referencias a registros creados al pagar (para no duplicar y poder revertir)
    gasto_mensual_id = models.PositiveIntegerField(null=True, blank=True)
    gasto_personal_id = models.PositiveIntegerField(null=True, blank=True)

    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pagos_futuros_creados",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pagado", "fecha_vencimiento", "-id"]
        verbose_name = "Pago futuro"
        verbose_name_plural = "Agenda de pagos"

    def __str__(self):
        return f"{self.descripcion} — ${self.monto} ({self.fecha_vencimiento})"

    @property
    def vencido(self):
        from datetime import date
        return (not self.pagado) and self.fecha_vencimiento < date.today()

    @property
    def vence_hoy(self):
        from datetime import date
        return (not self.pagado) and self.fecha_vencimiento == date.today()

    @property
    def dias_restantes(self):
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days

from django.db import models
from django.contrib.auth.models import User


class IngresoFuturo(models.Model):
    """
    Ingreso futuro programado (Agenda de Ingresos). Al marcarse como
    cobrado, se crea automáticamente el registro en el módulo destino:
    - Control de Ingresos → ingreso operativo de la concesionaria.
    - Ingresos Personales → ingreso personal del usuario que cobra.
    """

    DESTINO_CONTROL_INGRESOS = "control_ingresos"
    DESTINO_INGRESOS_PERSONALES = "ingresos_personales"
    DESTINO_CHOICES = [
        (DESTINO_CONTROL_INGRESOS, "Control de Ingresos"),
        (DESTINO_INGRESOS_PERSONALES, "Ingresos Personales"),
    ]

    FORMA_COBRO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("transferencia", "Transferencia"),
        ("cheque", "Cheque"),
        ("otro", "Otro"),
    ]

    descripcion = models.CharField("Descripción", max_length=200)
    concepto = models.CharField(
        "Concepto", max_length=120, blank=True,
        help_text="Ej: Alquiler, Venta, Comisión, Otro",
    )
    monto = models.DecimalField(
        "Monto", max_digits=14, decimal_places=2, default=0,
        help_text="Opcional al agendar. Se confirma al marcar como cobrado.",
    )
    fecha_vencimiento = models.DateField("Fecha de cobro estimada")

    destino = models.CharField(
        "Destino al cobrar", max_length=20, choices=DESTINO_CHOICES,
        default=DESTINO_CONTROL_INGRESOS,
        help_text="Control de Ingresos = ingreso de la concesionaria · "
                  "Ingresos Personales = ingreso del usuario que cobra.",
    )
    forma_cobro = models.CharField(
        "Forma de cobro", max_length=20, choices=FORMA_COBRO_CHOICES, blank=True,
    )

    es_recurrente_mensual = models.BooleanField(
        "Ingreso mensual recurrente", default=False,
        help_text="Si está activo, al cobrarse se agenda automáticamente el del mes siguiente.",
    )
    recurrente_hasta = models.DateField(
        "Recurrente hasta", null=True, blank=True,
        help_text="Solo si es recurrente: hasta qué fecha se sigue agendando. Vacío = sin límite.",
    )

    cobrado = models.BooleanField(default=False)
    fecha_cobro = models.DateField(null=True, blank=True)
    cobrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ingresos_futuros_cobrados",
    )

    observaciones = models.TextField(blank=True)

    # Referencias a los registros creados al cobrar (para no duplicar / revertir)
    ingreso_mensual_id = models.PositiveIntegerField(null=True, blank=True)
    ingreso_personal_id = models.PositiveIntegerField(null=True, blank=True)

    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ingresos_futuros_creados",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cobrado", "fecha_vencimiento", "-id"]
        verbose_name = "Ingreso futuro"
        verbose_name_plural = "Agenda de Ingresos"

    def __str__(self):
        return f"{self.descripcion} — ${self.monto} ({self.fecha_vencimiento})"

    @property
    def vencido(self):
        from datetime import date
        return (not self.cobrado) and self.fecha_vencimiento < date.today()

    @property
    def proxima_fecha_mensual(self):
        import calendar
        from datetime import date
        f = self.fecha_vencimiento
        year = f.year + (1 if f.month == 12 else 0)
        month = 1 if f.month == 12 else f.month + 1
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(f.day, last_day))

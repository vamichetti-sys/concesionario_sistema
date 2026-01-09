from django.db import models


# ==========================================================
# EMPLEADO
# ==========================================================
class Empleado(models.Model):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


# ==========================================================
# ASISTENCIA DIARIA
# ==========================================================
class AsistenciaDiaria(models.Model):

    ESTADOS = [
        ("presente", "Presente"),
        ("falta_justificada", "Falta Justificada"),
        ("falta_injustificada", "Falta Injustificada"),
        ("permiso", "Permiso"),
        ("vacaciones", "Vacaciones"),
        ("estudio", "Día por Estudio"),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name="asistencias"
    )

    fecha = models.DateField()

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="presente"
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        # 🔒 Evita doble asistencia el mismo día
        unique_together = ("empleado", "fecha")

        # 📅 Orden cronológico
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.empleado} - {self.fecha} ({self.get_estado_display()})"

    # ======================================================
    # 🔍 HELPERS EXISTENTES
    # ======================================================
    @property
    def cuenta_como_trabajado(self):
        """
        Indica si el día cuenta como trabajado.
        """
        return self.estado in [
            "presente",
            "permiso",
            "estudio",
        ]

    @property
    def es_falta(self):
        """
        Indica si el día fue una falta (justificada o no).
        """
        return self.estado in [
            "falta_justificada",
            "falta_injustificada",
        ]

    @property
    def es_ausencia(self):
        """
        Indica ausencia total (no trabajado).
        """
        return self.estado in [
            "falta_justificada",
            "falta_injustificada",
            "vacaciones",
        ]

    # ======================================================
    # 🆕 HELPERS PARA REPORTE WEB (NO ROMPEN NADA)
    # ======================================================
    @property
    def es_falta_injustificada(self):
        """True si la falta es injustificada."""
        return self.estado == "falta_injustificada"

    @property
    def es_falta_justificada(self):
        """True si la falta es justificada."""
        return self.estado == "falta_justificada"

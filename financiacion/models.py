from django.db import models


# ============================================================
# FINANCIERA
# ============================================================
class Financiera(models.Model):
    """
    Financiera con la que trabaja el concesionario. Cuando una venta se
    marca como "financiada", la financiera es quien asume la deuda de esa
    venta (es a quien después le cobramos).
    """

    nombre = models.CharField(
        "Nombre de fantasía",
        max_length=120,
    )
    cuit = models.CharField(
        "CUIT",
        max_length=20,
        blank=True,
        null=True,
    )
    contacto = models.CharField(
        "Persona de contacto",
        max_length=120,
        blank=True,
        null=True,
    )
    telefono = models.CharField(
        "Teléfono",
        max_length=50,
        blank=True,
        null=True,
    )
    notas = models.TextField(
        blank=True,
        null=True,
    )
    activa = models.BooleanField(
        default=True,
        help_text="Desmarcá para ocultarla de la lista al marcar ventas financiadas.",
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Financiera"
        verbose_name_plural = "Financieras"

    def __str__(self):
        return self.nombre

from django.db import models
from django.contrib.auth.models import User


class Contrasena(models.Model):
    """
    Credencial guardada en el gestor interno de contraseñas.
    El acceso está restringido por vista (solo Hamichetti y Vamichetti).
    """
    servicio = models.CharField("Servicio / Sitio", max_length=200)
    usuario = models.CharField("Usuario / Email", max_length=200, blank=True)
    contrasena = models.CharField("Contraseña", max_length=300)
    url = models.URLField("URL", blank=True)
    notas = models.TextField("Notas", blank=True)

    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["servicio"]
        verbose_name = "Contraseña"
        verbose_name_plural = "Contraseñas"

    def __str__(self):
        return self.servicio

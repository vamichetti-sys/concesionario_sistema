from django.db import models
from django.contrib.auth.models import User


class PermisoUsuario(models.Model):
    """
    Permisos de acceso por sección del menú para un usuario.
    Por defecto todo en True (no cambia el comportamiento existente hasta
    que un admin restrinja algo). Vamichetti/Hamichetti y superusers
    siempre tienen acceso total (no se consulta este modelo para ellos).
    """
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="permisos_secciones"
    )
    operaciones = models.BooleanField(default=True)
    clientes = models.BooleanField(default=True)
    documentacion = models.BooleanField(default=True)
    administracion = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Permiso de usuario"
        verbose_name_plural = "Permisos de usuarios"

    def __str__(self):
        return f"Permisos de {self.usuario.username}"

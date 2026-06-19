from django.db import models
from django.contrib.auth.models import User


class PermisoUsuario(models.Model):
    """
    Permisos de acceso del usuario, por ÍTEM del menú (granular).
    `claves` guarda la lista de ítems que el usuario puede ver
    (ej: ["vehiculos", "ventas", "clientes"]). Vacío = no ve nada.
    Vamichetti/Hamichetti y superusers siempre ven todo (no se consulta
    este modelo para ellos).
    """
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="permisos_secciones"
    )
    claves = models.JSONField(default=list, blank=True)
    # Si está en False, el usuario NO ve los precios de los vehículos
    # (listado, ficha y PDF). Admins siempre ven precios.
    ver_precio = models.BooleanField("Puede ver precios", default=True)

    class Meta:
        verbose_name = "Permiso de usuario"
        verbose_name_plural = "Permisos de usuarios"

    def __str__(self):
        return f"Permisos de {self.usuario.username}"

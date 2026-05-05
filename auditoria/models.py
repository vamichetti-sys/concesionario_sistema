from django.db import models
from django.contrib.auth.models import User


# ============================================================
# LOG DE ACTIVIDAD / AUDITORÍA
# ============================================================
class LogActividad(models.Model):
    ACCIONES = [
        ("crear", "Crear"),
        ("editar", "Editar"),
        ("eliminar", "Eliminar"),
        ("login", "Inicio de sesión"),
        ("logout", "Cierre de sesión"),
        ("login_fallido", "Login fallido"),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    usuario_texto = models.CharField(
        max_length=150,
        blank=True,
        help_text="Guardamos el nombre por si se borra el usuario",
    )
    accion = models.CharField(max_length=20, choices=ACCIONES)
    modelo = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tabla afectada (ej: Vehiculo, Venta, Pago)",
    )
    objeto_id = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=500)
    datos_antes = models.JSONField(blank=True, null=True)
    datos_despues = models.JSONField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Log de actividad"
        verbose_name_plural = "Logs de actividad"
        indexes = [
            models.Index(fields=["-fecha"]),
            models.Index(fields=["usuario", "-fecha"]),
            models.Index(fields=["modelo", "-fecha"]),
        ]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} - {self.usuario_texto} - {self.get_accion_display()} - {self.modelo}"

    @classmethod
    def registrar(cls, usuario, accion, modelo="", objeto_id="", descripcion="",
                  datos_antes=None, datos_despues=None, ip=None):
        """Helper para crear un log desde cualquier lugar."""
        return cls.objects.create(
            usuario=usuario if usuario and usuario.is_authenticated else None,
            usuario_texto=(usuario.username if usuario and usuario.is_authenticated else "Anónimo"),
            accion=accion,
            modelo=modelo,
            objeto_id=str(objeto_id) if objeto_id else "",
            descripcion=descripcion,
            datos_antes=datos_antes,
            datos_despues=datos_despues,
            ip=ip,
        )

    def cambios(self):
        """
        Devuelve lista de (campo, antes, despues) con los campos que cambiaron.
        Usado por el template de auditoría para mostrar el diff.
        """
        if not self.datos_antes:
            return []
        labels = self._labels_de_campos()
        despues = self.datos_despues or {}
        resultado = []
        for campo, val_antes in self.datos_antes.items():
            val_despues = despues.get(campo)
            etiqueta = labels.get(
                campo, campo.replace("_", " ").capitalize()
            )
            resultado.append((etiqueta, val_antes, val_despues))
        return resultado

    def _labels_de_campos(self):
        """
        Resuelve verbose_name de cada campo del modelo afectado para mostrar
        etiquetas legibles en el diff.
        """
        from django.apps import apps as _apps
        if not self.modelo:
            return {}
        try:
            for Model in _apps.get_models():
                if Model.__name__ == self.modelo:
                    out = {}
                    for f in Model._meta.fields:
                        verbose = getattr(f, "verbose_name", None)
                        out[f.name] = (
                            str(verbose).capitalize()
                            if verbose
                            else f.name.replace("_", " ").capitalize()
                        )
                    return out
        except Exception:
            pass
        return {}

from django.db import models
from vehiculos.models import Vehiculo


# ============================================================
# FOTOS DEL VEHÍCULO
# ============================================================
class FotoVehiculo(models.Model):
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="fotos",
    )
    imagen = models.ImageField(
        upload_to="vehiculos/fotos/",
        verbose_name="Foto",
    )
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="Orden")
    es_portada = models.BooleanField(default=False, verbose_name="Foto de portada")
    subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "-subida"]
        verbose_name = "Foto de vehículo"
        verbose_name_plural = "Fotos de vehículos"

    def __str__(self):
        return f"Foto {self.id} – {self.vehiculo}"

    def save(self, *args, **kwargs):
        if self.es_portada:
            FotoVehiculo.objects.filter(
                vehiculo=self.vehiculo, es_portada=True
            ).exclude(pk=self.pk).update(es_portada=False)
        super().save(*args, **kwargs)


# ============================================================
# CONTROL DE PUBLICACIÓN EN PLATAFORMAS
# ============================================================
class PublicacionPlataforma(models.Model):
    PLATAFORMAS = [
        ("mercadolibre", "MercadoLibre"),
        ("facebook", "Facebook Marketplace"),
        ("instagram", "Instagram"),
        ("web", "Página web"),
    ]

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="publicaciones",
    )
    plataforma = models.CharField(
        max_length=20,
        choices=PLATAFORMAS,
    )
    publicado = models.BooleanField(default=False)
    fecha_publicacion = models.DateField(blank=True, null=True)
    observacion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        unique_together = ["vehiculo", "plataforma"]
        ordering = ["plataforma"]
        verbose_name = "Publicación"
        verbose_name_plural = "Publicaciones"

    def __str__(self):
        estado = "Publicado" if self.publicado else "Pendiente"
        return f"{self.vehiculo} – {self.get_plataforma_display()} ({estado})"

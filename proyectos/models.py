from django.db import models
from django.conf import settings
from django.utils import timezone


# ==========================================================
# PROYECTO
# Contenedor de tareas. Cada usuario maneja sus propios proyectos.
# ==========================================================
class Proyecto(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proyectos',
    )
    nombre = models.CharField(max_length=120)
    # Color en formato hex (#rrggbb) usado como acento del proyecto en UI
    color = models.CharField(max_length=7, default='#e8820a')
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activo', '-created_at']
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'

    def __str__(self):
        return self.nombre

    @property
    def total_tareas(self):
        return self.tareas.count()

    @property
    def tareas_hechas(self):
        return self.tareas.filter(estado='hecha').count()

    @property
    def progreso(self):
        # Porcentaje de tareas completadas (0 a 100, entero)
        total = self.total_tareas
        if not total:
            return 0
        return int(round((self.tareas_hechas / total) * 100))


# ==========================================================
# TAREA
# Unidad de trabajo asociada a un proyecto.
# ==========================================================
class Tarea(models.Model):
    ESTADO_CHOICES = [
        ('pend', 'Pendiente'),
        ('curso', 'En curso'),
        ('hecha', 'Hecha'),
        ('bloq', 'Bloqueada'),
    ]
    PRIORIDAD_CHOICES = [
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tareas_proyecto',
    )
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='tareas',
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='pend',
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='media',
    )
    deadline = models.DateTimeField(null=True, blank=True)
    completada_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Vencidas y altas primero; sin fecha al final
        ordering = ['deadline', '-prioridad', '-created_at']
        verbose_name = 'Tarea'
        verbose_name_plural = 'Tareas'

    def __str__(self):
        return self.titulo

    def esta_vencida(self):
        # Vencida solo si tiene deadline, está pasada y la tarea no está hecha
        if not self.deadline:
            return False
        if self.estado == 'hecha':
            return False
        return self.deadline < timezone.now()

    @property
    def dias_restantes(self):
        # Días enteros hasta el deadline; negativos = vencida; None si no hay deadline
        if not self.deadline:
            return None
        delta = self.deadline - timezone.now()
        return delta.days

    def save(self, *args, **kwargs):
        # Si pasa a "hecha" y no tenía fecha de completado, la setea ahora
        if self.estado == 'hecha' and not self.completada_en:
            self.completada_en = timezone.now()
        # Si la des-marcan como hecha, limpiamos la fecha
        if self.estado != 'hecha' and self.completada_en:
            self.completada_en = None
        super().save(*args, **kwargs)


# ==========================================================
# RECORDATORIO
# Aviso programado, opcionalmente atado a una tarea.
# ==========================================================
class Recordatorio(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recordatorios_proyecto',
    )
    tarea = models.ForeignKey(
        Tarea,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recordatorios',
    )
    titulo = models.CharField(max_length=200)
    fecha_hora = models.DateTimeField()
    notificado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_hora']
        verbose_name = 'Recordatorio'
        verbose_name_plural = 'Recordatorios'

    def __str__(self):
        return self.titulo

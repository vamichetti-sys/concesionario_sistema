from django.db import models
from django.utils import timezone


# ==========================================================
# CONVERSACIÓN
# Un hilo de mensajes con un contacto de Instagram o Messenger.
# ==========================================================
class ConversacionMeta(models.Model):
    PLATAFORMAS = [
        ("instagram", "Instagram"),
        ("messenger", "Messenger"),
    ]

    plataforma = models.CharField(max_length=20, choices=PLATAFORMAS)
    # ID del contacto que da Meta (PSID en Messenger / IGSID en Instagram)
    contacto_id = models.CharField(max_length=120)
    nombre = models.CharField(max_length=150, blank=True, default="")
    foto_url = models.URLField(blank=True, default="")

    ultimo_texto = models.TextField(blank=True, default="")
    ultima_fecha = models.DateTimeField(null=True, blank=True)
    no_leido = models.BooleanField(default=True)

    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ultima_fecha", "-id"]
        unique_together = ("plataforma", "contacto_id")
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"

    def __str__(self):
        return f"{self.get_plataforma_display()} · {self.nombre or self.contacto_id}"


# ==========================================================
# MENSAJE
# Cada mensaje individual dentro de una conversación.
# ==========================================================
class MensajeMeta(models.Model):
    conversacion = models.ForeignKey(
        ConversacionMeta,
        on_delete=models.CASCADE,
        related_name="mensajes",
    )
    # True = lo escribió el contacto (entrante); False = lo respondimos nosotros
    entrante = models.BooleanField(default=True)
    texto = models.TextField(blank=True, default="")
    # ID del mensaje en Meta (para no duplicar al recibir el webhook)
    mid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"

    def __str__(self):
        sentido = "←" if self.entrante else "→"
        return f"{sentido} {self.texto[:40]}"


# ==========================================================
# LEAD
# Contacto capturado de un formulario de anuncios (Lead Ads).
# Queda acá como registro y además se crea un Prospecto en el CRM.
# ==========================================================
class LeadMeta(models.Model):
    PLATAFORMAS = [
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
    ]

    plataforma = models.CharField(max_length=20, choices=PLATAFORMAS, default="facebook")
    leadgen_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    form_id = models.CharField(max_length=120, blank=True, default="")

    nombre = models.CharField(max_length=150, blank=True, default="")
    telefono = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    # Datos crudos del formulario (todos los campos que mande Meta)
    datos = models.JSONField(default=dict, blank=True)

    prospecto = models.ForeignKey(
        "crm.Prospecto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_meta",
    )

    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"{self.nombre or 'Lead'} ({self.get_plataforma_display()})"

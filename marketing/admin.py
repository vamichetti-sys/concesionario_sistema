from django.contrib import admin
from .models import ConversacionMeta, MensajeMeta, LeadMeta


@admin.register(ConversacionMeta)
class ConversacionMetaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plataforma", "ultima_fecha", "no_leido")
    list_filter = ("plataforma", "no_leido")
    search_fields = ("nombre", "contacto_id")


@admin.register(MensajeMeta)
class MensajeMetaAdmin(admin.ModelAdmin):
    list_display = ("conversacion", "entrante", "texto", "fecha")
    list_filter = ("entrante",)


@admin.register(LeadMeta)
class LeadMetaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plataforma", "telefono", "email", "fecha")
    list_filter = ("plataforma",)
    search_fields = ("nombre", "telefono", "email")

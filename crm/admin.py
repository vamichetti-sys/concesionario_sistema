from django.contrib import admin
from .models import Prospecto, Seguimiento


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "etapa", "origen", "prioridad", "fecha_creacion")
    list_filter = ("etapa", "origen", "prioridad")
    search_fields = ("nombre_completo", "telefono", "email")


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ("prospecto", "tipo", "creado_por", "fecha")
    list_filter = ("tipo",)

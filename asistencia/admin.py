from django.contrib import admin
from .models import Empleado, AsistenciaDiaria


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)


@admin.register(AsistenciaDiaria)
class AsistenciaDiariaAdmin(admin.ModelAdmin):
    list_display = ("empleado", "fecha", "estado")
    list_filter = ("estado", "empleado")
    date_hierarchy = "fecha"

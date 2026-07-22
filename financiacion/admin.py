from django.contrib import admin

from .models import Financiera


@admin.register(Financiera)
class FinancieraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuit", "contacto", "telefono", "activa", "creada")
    list_filter = ("activa",)
    search_fields = ("nombre", "cuit", "contacto")

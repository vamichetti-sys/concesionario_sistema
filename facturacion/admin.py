from django.contrib import admin
from .models import FacturaRegistrada


@admin.register(FacturaRegistrada)
class FacturaRegistradaAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "monto", "venta")
    list_filter = ("fecha",)
    search_fields = ("numero",)

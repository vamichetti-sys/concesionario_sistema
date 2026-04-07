from django.contrib import admin
from .models import FacturaRegistrada, CompraRegistrada


@admin.register(FacturaRegistrada)
class FacturaRegistradaAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "monto", "venta")
    list_filter = ("fecha",)
    search_fields = ("numero",)


@admin.register(CompraRegistrada)
class CompraRegistradaAdmin(admin.ModelAdmin):
    list_display = ("numero", "proveedor", "fecha", "monto")
    list_filter = ("fecha",)
    search_fields = ("numero", "proveedor")

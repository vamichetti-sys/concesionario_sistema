from django.contrib import admin
from .models import Proveedor, CompraVentaOperacion, DeudaProveedor, PagoProveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre_empresa", "cuit", "activo")
    search_fields = ("nombre_empresa", "cuit")
    list_filter = ("activo",)


@admin.register(CompraVentaOperacion)
class CompraVentaOperacionAdmin(admin.ModelAdmin):
    list_display = ("vehiculo", "origen", "proveedor", "precio_compra", "estado")
    list_filter = ("origen", "estado")


@admin.register(DeudaProveedor)
class DeudaProveedorAdmin(admin.ModelAdmin):
    list_display = ("proveedor", "vehiculo", "monto_total")


@admin.register(PagoProveedor)
class PagoProveedorAdmin(admin.ModelAdmin):
    list_display = ("deuda", "fecha", "monto")

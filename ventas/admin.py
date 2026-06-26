from django.contrib import admin

from .models import Venta, CuentaVendedor, MovimientoComision


@admin.register(CuentaVendedor)
class CuentaVendedorAdmin(admin.ModelAdmin):
    list_display = ("vendedor", "saldo", "activa", "fecha_creacion")
    search_fields = ("vendedor__username", "vendedor__first_name", "vendedor__last_name")
    list_filter = ("activa",)


@admin.register(MovimientoComision)
class MovimientoComisionAdmin(admin.ModelAdmin):
    list_display = ("cuenta", "tipo", "monto", "descripcion", "fecha", "venta")
    list_filter = ("tipo", "fecha")
    search_fields = ("cuenta__vendedor__username", "descripcion")
    raw_id_fields = ("venta",)

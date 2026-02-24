from django.contrib import admin
from .models import Presupuesto


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre_cliente', 'vehiculo', 'precio_final', 'estado', 'fecha_creacion']
    list_filter = ['estado', 'moneda', 'forma_pago']
    search_fields = ['nombre_cliente', 'vehiculo__marca', 'vehiculo__modelo']
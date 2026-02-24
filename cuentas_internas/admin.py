from django.contrib import admin
from .models import CuentaInterna, MovimientoInterno


@admin.register(CuentaInterna)
class CuentaInternaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'cargo', 'saldo', 'activa', 'fecha_creacion']
    list_filter = ['activa']
    search_fields = ['nombre', 'cargo']


@admin.register(MovimientoInterno)
class MovimientoInternoAdmin(admin.ModelAdmin):
    list_display = ['cuenta', 'tipo', 'monto', 'concepto', 'fecha']
    list_filter = ['tipo', 'fecha']
    search_fields = ['concepto', 'cuenta__nombre']
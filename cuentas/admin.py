from django.contrib import admin
from .models import (
    CuentaCorriente,
    MovimientoCuenta,
    PlanPago,
    CuotaPlan
)


@admin.register(CuentaCorriente)
class CuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'venta', 'saldo', 'estado')
    search_fields = ('cliente__nombre', 'cliente__apellido')


@admin.register(MovimientoCuenta)
class MovimientoCuentaAdmin(admin.ModelAdmin):
    list_display = ('cuenta', 'fecha', 'tipo', 'monto')


@admin.register(PlanPago)
class PlanPagoAdmin(admin.ModelAdmin):
    list_display = ('cuenta', 'cantidad_cuotas', 'monto_cuota', 'estado')


@admin.register(CuotaPlan)
class CuotaPlanAdmin(admin.ModelAdmin):
    list_display = ('plan', 'numero', 'monto', 'estado')

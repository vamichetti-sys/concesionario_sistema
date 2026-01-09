from django.contrib import admin
from .models import Cliente, ReglaComercial
from .services import recalcular_cumplimiento_cliente


# ==========================================================
# ADMIN DE CLIENTES
# ==========================================================
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):

    # ======== LISTADO ========
    list_display = (
        'nombre_completo',
        'telefono',
        'email',
        'dni_cuit',
        'cumplimiento_pago',
        'fecha_alta',
    )

    # ======== BÚSQUEDA ========
    search_fields = (
        'nombre_completo',
        'telefono',
        'email',
        'dni_cuit',
    )

    # ======== FILTROS ========
    list_filter = (
        'cumplimiento_pago',
        'fecha_alta',
    )

    # ======== ACCIONES ========
    actions = ['recalcular_cumplimiento']

    def recalcular_cumplimiento(self, request, queryset):
        """
        Recalcula el cumplimiento de pago del/los cliente/s seleccionados
        según sus cuentas corrientes y cuotas.
        """
        for cliente in queryset:
            recalcular_cumplimiento_cliente(cliente)

        self.message_user(
            request,
            'Cumplimiento de pago recalculado correctamente.'
        )

    recalcular_cumplimiento.short_description = (
        'Recalcular cumplimiento de pago del cliente'
    )


# ==========================================================
# ADMIN DE REGLAS COMERCIALES
# ==========================================================
@admin.register(ReglaComercial)
class ReglaComercialAdmin(admin.ModelAdmin):

    list_display = (
        'color_cliente',
        'permite_financiacion',
        'anticipo_minimo_porcentaje',
        'max_cuotas',
        'acepta_cheques',
    )

    list_filter = (
        'color_cliente',
    )

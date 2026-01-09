from django.contrib import admin
from .models import ReporteMensual, ReporteAnual


# ==========================================================
# REPORTE MENSUAL
# ==========================================================
@admin.register(ReporteMensual)
class ReporteMensualAdmin(admin.ModelAdmin):
    list_display = (
        "mes",
        "anio",
        "total_facturado",
        "fecha_cierre",
    )
    list_filter = (
        "anio",
        "mes",
    )
    ordering = ("-anio", "-mes")
    search_fields = ("anio",)


# ==========================================================
# REPORTE ANUAL
# ==========================================================
@admin.register(ReporteAnual)
class ReporteAnualAdmin(admin.ModelAdmin):
    list_display = (
        "anio",
        "total_facturado",
        "fecha_cierre",
    )
    ordering = ("-anio",)
    search_fields = ("anio",)

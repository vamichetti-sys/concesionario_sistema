from django.contrib import admin
from .models import CategoriaGasto, GastoMensual, ResumenGastosMensual


@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "es_fijo", "activa")
    list_filter = ("es_fijo", "activa")


@admin.register(GastoMensual)
class GastoMensualAdmin(admin.ModelAdmin):
    list_display = ("categoria", "monto", "mes", "anio", "unidad", "pagado")
    list_filter = ("anio", "mes", "pagado", "unidad", "categoria")


@admin.register(ResumenGastosMensual)
class ResumenGastosMensualAdmin(admin.ModelAdmin):
    list_display = ("mes", "anio", "total_general", "total_pagado", "total_pendiente")

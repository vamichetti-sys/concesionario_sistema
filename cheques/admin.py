from django.contrib import admin
from .models import Cheque


@admin.register(Cheque)
class ChequeAdmin(admin.ModelAdmin):
    list_display = ['numero', 'tipo', 'banco', 'titular', 'monto', 'fecha_cobro', 'estado']
    list_filter = ['tipo', 'estado', 'banco']
    search_fields = ['numero', 'titular', 'banco', 'origen_destino']
from django.contrib import admin
from .models import Cheque


@admin.register(Cheque)
class ChequeAdmin(admin.ModelAdmin):
    list_display = ['numero_cheque', 'cliente', 'banco_emision', 'titular_cheque', 'monto', 'fecha_deposito', 'estado']
    list_filter = ['estado', 'banco_emision']
    search_fields = ['numero_cheque', 'titular_cheque', 'cliente', 'banco_emision']
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fecha", "vehiculo")

    def save_model(self, request, obj, form, change):
        # 🔒 BLOQUEO DEFINITIVO DE VENCIMIENTOS
        if obj.titulo and "vencimiento" in obj.titulo.lower():
            raise ValidationError(
                "Los vencimientos se cargan desde la ficha del vehículo"
            )
        super().save_model(request, obj, form, change)

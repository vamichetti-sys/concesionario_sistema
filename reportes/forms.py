from django import forms
from .models import (
    FichaReporteInterno,
    GastoReporteInterno,
)


# ==========================================================
# FORMULARIOS DE REPORTES
# ==========================================================


class FiltroReporteForm(forms.Form):
    """
    Formulario base para filtros de reportes
    (fechas, estados, etc.)
    """
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control"
            }
        )
    )

    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "form-control"
            }
        )
    )


# ==========================================================
# EDICIÓN DE FICHA INTERNA (REPORTE INTERNO)
# 👉 SIN total_gastos (ahora es automático)
# ==========================================================
class FichaReporteInternoForm(forms.ModelForm):
    """
    Formulario para editar la ficha interna del vehículo
    (compra / venta / comprador)
    """

    class Meta:
        model = FichaReporteInterno
        fields = [
            "fecha_compra",
            "precio_compra",
            "fecha_venta",
            "precio_venta",
            "comprador",
        ]

        widgets = {
            "fecha_compra": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "class": "form-control"
                }
            ),
            "fecha_venta": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "class": "form-control"
                }
            ),
            "precio_compra": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01"
                }
            ),
            "precio_venta": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01"
                }
            ),
            "comprador": forms.TextInput(
                attrs={
                    "class": "form-control"
                }
            ),
        }


# ==========================================================
# GASTOS INTERNOS DEL REPORTE
# 👉 Carga individual de gastos
# ==========================================================
class GastoReporteInternoForm(forms.ModelForm):
    """
    Formulario para agregar un gasto individual
    al reporte interno del vehículo.
    """

    class Meta:
        model = GastoReporteInterno
        fields = ["concepto", "monto"]

        widgets = {
            "concepto": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Gestoría, transferencia, reparación"
                }
            ),
            "monto": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01"
                }
            ),
        }

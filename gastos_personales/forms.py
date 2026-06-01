from django import forms

from gastos_mensuales.models import CategoriaGasto
from .models import GastoPersonal, IngresoPersonal

_MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


class GastoPersonalForm(forms.ModelForm):
    class Meta:
        model = GastoPersonal
        fields = ["categoria", "descripcion", "monto", "mes", "anio", "pagado", "fecha_pago", "observaciones"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Detalle del gasto"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}),
            "mes": forms.Select(
                choices=[(i, n) for i, n in enumerate(_MESES, start=0) if i > 0],
                attrs={"class": "form-select"},
            ),
            "anio": forms.NumberInput(attrs={"class": "form-control", "placeholder": "2026"}),
            "pagado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "fecha_pago": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaGasto.objects.filter(activa=True)


class IngresoPersonalForm(forms.ModelForm):
    class Meta:
        model = IngresoPersonal
        fields = ["concepto", "descripcion", "monto", "mes", "anio", "fecha", "observaciones"]
        widgets = {
            "concepto": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Sueldo, Venta, Alquiler cobrado"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Detalle del ingreso"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}),
            "mes": forms.Select(choices=[(i, n) for i, n in enumerate(_MESES) if i > 0], attrs={"class": "form-select"}),
            "anio": forms.NumberInput(attrs={"class": "form-control", "placeholder": "2026"}),
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas..."}),
        }

from django import forms
from .models import CategoriaGasto, GastoMensual


class CategoriaGastoForm(forms.ModelForm):
    class Meta:
        model = CategoriaGasto
        fields = ["nombre", "descripcion", "es_fijo"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: Alquiler, Sueldos, Publicidad...",
            }),
            "descripcion": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Descripcion opcional",
            }),
            "es_fijo": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }


class GastoMensualForm(forms.ModelForm):
    class Meta:
        model = GastoMensual
        fields = [
            "categoria",
            "descripcion",
            "monto",
            "mes",
            "anio",
            "unidad",
            "pagado",
            "fecha_pago",
            "observaciones",
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Detalle del gasto",
            }),
            "monto": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "0.00",
                "step": "0.01",
            }),
            "mes": forms.Select(
                choices=[(i, n) for i, n in enumerate(
                    ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
                    start=0
                ) if i > 0],
                attrs={"class": "form-select"},
            ),
            "anio": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "2026",
            }),
            "unidad": forms.Select(attrs={"class": "form-select"}),
            "pagado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "fecha_pago": forms.DateInput(format="%Y-%m-%d", attrs={
                "class": "form-control",
                "type": "date",
            }),
            "observaciones": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Notas...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaGasto.objects.filter(activa=True)

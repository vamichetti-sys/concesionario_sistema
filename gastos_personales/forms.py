from django import forms
from .models import GastoPersonal


class GastoPersonalForm(forms.ModelForm):
    class Meta:
        model = GastoPersonal
        fields = ["fecha", "concepto", "categoria", "monto", "notas"]
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "concepto": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Supermercado, Nafta"}),
            "categoria": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Comida, Transporte (opcional)"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "notas": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas opcionales"}),
        }

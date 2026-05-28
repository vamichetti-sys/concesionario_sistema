from django import forms

from gastos_mensuales.models import CategoriaGasto
from .models import PagoFuturo


class PagoFuturoForm(forms.ModelForm):
    class Meta:
        model = PagoFuturo
        fields = [
            "descripcion", "monto", "fecha_vencimiento",
            "categoria", "destino",
            "observaciones",
        ]
        widgets = {
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Alquiler local, Celular, Impuestos..."}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "fecha_vencimiento": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "destino": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas opcionales"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaGasto.objects.filter(activa=True)
        self.fields["categoria"].required = False
        self.fields["observaciones"].required = False


class MarcarPagadoForm(forms.Form):
    fecha_pago = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    forma_pago = forms.ChoiceField(
        choices=PagoFuturo.FORMA_PAGO_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
    )

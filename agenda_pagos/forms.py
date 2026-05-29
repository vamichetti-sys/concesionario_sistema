from django import forms

from gastos_mensuales.models import CategoriaGasto
from .models import PagoFuturo


class PagoFuturoForm(forms.ModelForm):
    """Form para AGENDAR un pago futuro. El monto es opcional acá: se va a
    pedir cuando se marque como pagado."""

    class Meta:
        model = PagoFuturo
        fields = [
            "descripcion", "monto", "fecha_vencimiento",
            "categoria", "destino", "es_recurrente_mensual",
            "observaciones",
        ]
        widgets = {
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Alquiler local, Celular, Impuestos..."}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "Opcional"}),
            "fecha_vencimiento": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "destino": forms.Select(attrs={"class": "form-select"}),
            "es_recurrente_mensual": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas opcionales"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaGasto.objects.filter(activa=True)
        self.fields["categoria"].required = False
        self.fields["observaciones"].required = False
        self.fields["monto"].required = False  # se completa al marcar pagado


class MarcarPagadoForm(forms.Form):
    """Form para MARCAR un pago como pagado. Acá sí se pide el monto real."""
    monto = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        help_text="Monto exacto pagado. Se vuelca al módulo destino.",
    )
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
    agregar_mes_siguiente = forms.BooleanField(
        required=False,
        label="Agendar también el mes siguiente",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Si está tildado, se crea un nuevo pago en la agenda con la misma descripción y vencimiento +1 mes.",
    )

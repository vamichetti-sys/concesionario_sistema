from django import forms

from .models import IngresoFuturo


class IngresoFuturoForm(forms.ModelForm):
    """Agendar un ingreso futuro. El monto es opcional acá."""

    class Meta:
        model = IngresoFuturo
        fields = [
            "descripcion", "concepto", "monto", "fecha_vencimiento",
            "destino", "es_recurrente_mensual", "recurrente_hasta",
            "observaciones",
        ]
        widgets = {
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Alquiler local, Venta unidad..."}),
            "concepto": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Alquiler, Venta, Comisión"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "Opcional"}),
            "fecha_vencimiento": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "destino": forms.Select(attrs={"class": "form-select"}),
            "es_recurrente_mensual": forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_es_recurrente_mensual"}),
            "recurrente_hasta": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas opcionales"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concepto"].required = False
        self.fields["monto"].required = False
        self.fields["observaciones"].required = False
        self.fields["recurrente_hasta"].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("es_recurrente_mensual"):
            cleaned["recurrente_hasta"] = None
        return cleaned


class MarcarCobradoForm(forms.Form):
    """Marcar un ingreso como cobrado: acá se confirma el monto real."""
    monto = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        help_text="Monto exacto cobrado. Se vuelca al módulo destino.",
    )
    fecha_cobro = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    forma_cobro = forms.ChoiceField(
        choices=IngresoFuturo.FORMA_COBRO_CHOICES,
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
    )

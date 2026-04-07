from django import forms
from .models import Prospecto, Seguimiento
from vehiculos.models import Vehiculo


class ProspectoForm(forms.ModelForm):
    class Meta:
        model = Prospecto
        fields = [
            "nombre_completo",
            "telefono",
            "email",
            "origen",
            "etapa",
            "prioridad",
            "vehiculo_interes",
            "vehiculo_interes_texto",
            "asignado_a",
            "fecha_proximo_contacto",
            "observaciones",
        ]
        widgets = {
            "nombre_completo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre y apellido",
            }),
            "telefono": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Teléfono de contacto",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Email",
            }),
            "origen": forms.Select(attrs={"class": "form-select"}),
            "etapa": forms.Select(attrs={"class": "form-select"}),
            "prioridad": forms.Select(attrs={"class": "form-select"}),
            "vehiculo_interes": forms.Select(attrs={"class": "form-select"}),
            "vehiculo_interes_texto": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: Toyota Corolla 2020",
            }),
            "asignado_a": forms.Select(attrs={"class": "form-select"}),
            "fecha_proximo_contacto": forms.DateInput(format="%Y-%m-%d", attrs={
                "class": "form-control",
                "type": "date",
            }),
            "observaciones": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Notas adicionales...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehiculo_interes"].queryset = Vehiculo.objects.filter(
            estado="stock"
        )
        self.fields["vehiculo_interes"].required = False
        self.fields["asignado_a"].required = False


class SeguimientoForm(forms.ModelForm):
    class Meta:
        model = Seguimiento
        fields = ["tipo", "descripcion"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Detalle del contacto...",
            }),
        }

from django import forms

from .models import Financiera


class FinancieraForm(forms.ModelForm):
    class Meta:
        model = Financiera
        fields = ["nombre", "cuit", "contacto", "telefono", "notas", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre de fantasía",
                "autofocus": "autofocus",
            }),
            "cuit": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "20-12345678-9 (opcional)",
            }),
            "contacto": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Persona de contacto (opcional)",
            }),
            "telefono": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Teléfono (opcional)",
            }),
            "notas": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Notas (opcional)",
            }),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

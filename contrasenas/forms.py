from django import forms
from .models import Contrasena


class ContrasenaForm(forms.ModelForm):
    class Meta:
        model = Contrasena
        fields = ["servicio", "usuario", "contrasena", "url", "notas"]
        widgets = {
            "servicio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Banco Nación, Gmail, AFIP"}),
            "usuario": forms.TextInput(attrs={"class": "form-control", "placeholder": "Usuario o email"}),
            "contrasena": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contraseña"}),
            "url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "notas": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Notas opcionales"}),
        }

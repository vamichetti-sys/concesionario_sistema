from django import forms
from .models import Gestoria


class GestoriaForm(forms.ModelForm):
    class Meta:
        model = Gestoria
        fields = [
            # ===============================
            # ADMINISTRATIVO
            # ===============================
            "monto_transferencia",
            "pago_concesionaria_gestionado",
            "transferido",

            # ===============================
            # ESTADO / OBSERVACIONES
            # ===============================
            "estado",
            "observaciones",
        ]

        widgets = {
            # ===============================
            # ADMINISTRATIVO
            # ===============================
            "monto_transferencia": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0"
                }
            ),
            "pago_concesionaria_gestionado": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "transferido": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),

            # ===============================
            # ESTADO
            # ===============================
            "estado": forms.Select(
                attrs={"class": "form-select"}
            ),

            # ===============================
            # OBSERVACIONES
            # ===============================
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Observaciones internas de la gestoría"
                }
            ),
        }

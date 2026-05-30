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
            "pago_escribania",
            "pago_cliente",
            "pago_concesionaria",
            "pagado",
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
            "pago_escribania": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0,00",
                }
            ),
            "pago_cliente": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0,00",
                }
            ),
            "pago_concesionaria": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0,00",
                }
            ),
            "pagado": forms.CheckboxInput(
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

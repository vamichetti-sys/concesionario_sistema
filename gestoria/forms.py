from django import forms
from .models import Gestoria


class GestoriaForm(forms.ModelForm):
    class Meta:
        model = Gestoria
        fields = [
            # ===============================
            # DOCUMENTACIÓN
            # ===============================
            "formulario_08",
            "titulo",
            "cedula",
            "informe_dominio",

            # ===============================
            # ADMINISTRATIVO (AGREGADO)
            # ===============================
            "monto_transferencia",
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
            # CHECKBOXES DOCUMENTACIÓN
            # ===============================
            "formulario_08": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "titulo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "cedula": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "informe_dominio": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),

            # ===============================
            # ADMINISTRATIVO (AGREGADO)
            # ===============================
            "monto_transferencia": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0"
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

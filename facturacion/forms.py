from decimal import Decimal
from django import forms
from .models import FacturaRegistrada, CompraRegistrada


class FacturaRegistradaForm(forms.ModelForm):
    class Meta:
        model = FacturaRegistrada

        # 🔒 NO sacamos ningún campo existente
        # monto sigue siendo el TOTAL
        fields = [
            "venta",
            "numero",
            "fecha",
            "descripcion",
            "monto_neto",
            "iva_porcentaje",
            "monto_iva",
            "monto",
        ]

        widgets = {
            "venta": forms.Select(
                attrs={"class": "form-select"}
            ),

            "numero": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "fecha": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),

            "descripcion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Servicio, honorarios, alquiler..."
                }
            ),

            # ======================
            # 💰 IMPORTES
            # ======================
            "monto_neto": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Monto neto"
                }
            ),

            "iva_porcentaje": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01"
                }
            ),

            # 🔒 Calculado automáticamente
            "monto_iva": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "readonly": "readonly"
                }
            ),

            # 🔒 TOTAL FACTURADO
            "monto": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "readonly": "readonly"
                }
            ),
        }

    def clean(self):
        """
        Recalcula IVA y total al validar el formulario.
        No rompe facturas viejas.
        """
        cleaned_data = super().clean()

        monto_neto = cleaned_data.get("monto_neto")
        iva_porcentaje = cleaned_data.get("iva_porcentaje")

        if monto_neto is not None and iva_porcentaje is not None:
            iva = (monto_neto * iva_porcentaje) / 100
            cleaned_data["monto_iva"] = round(iva, 2)
            cleaned_data["monto"] = round(monto_neto + iva, 2)

        return cleaned_data


class CompraRegistradaForm(forms.ModelForm):
    class Meta:
        model = CompraRegistrada
        fields = [
            "numero", "proveedor", "fecha", "descripcion",
            "monto_neto", "iva_porcentaje",
            "otros_impuestos",
        ]
        widgets = {
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "proveedor": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre del proveedor",
            }),
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "descripcion": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Descripcion de la compra",
            }),
            "monto_neto": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01",
                "placeholder": "Monto neto",
            }),
            "iva_porcentaje": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01",
            }),
            "otros_impuestos": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.01",
                "placeholder": "Tasas, percepciones, etc.",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto_neto"].required = True

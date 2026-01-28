from django import forms
from .models import (
    Proveedor,
    CompraVentaOperacion,
    PagoProveedor,
    DeudaProveedor,
)

# ==========================================================
# 🏢 PROVEEDOR / AGENCIA
# ==========================================================
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre_empresa", "cuit", "activo"]
        labels = {
            "nombre_empresa": "Nombre de la empresa",
            "cuit": "CUIT",
            "activo": "Proveedor activo",
        }
        widgets = {
            "nombre_empresa": forms.TextInput(attrs={
                "class": "form-control am-input",
                "placeholder": "Nombre de la empresa",
            }),
            "cuit": forms.TextInput(attrs={
                "class": "form-control am-input",
                "placeholder": "00-00000000-0",
            }),
            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input am-switch",
            }),
        }


# ==========================================================
# 🔁 COMPRA / INGRESO DE VEHÍCULO
# ==========================================================
class CompraOperacionForm(forms.ModelForm):
    class Meta:
        model = CompraVentaOperacion
        fields = [
            "vehiculo",
            "origen",
            "proveedor",
            "fecha_compra",
            "precio_compra",
            "estado",
        ]
        widgets = {
            "fecha_compra": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "precio_compra": forms.NumberInput(attrs={
                "class": "form-control",
            }),
            "gastos_ingreso": forms.NumberInput(attrs={
                "class": "form-control",
            }),
            "origen": forms.Select(attrs={
                "class": "form-select",
            }),
            "proveedor": forms.Select(attrs={
                "class": "form-select",
            }),
            "vehiculo": forms.Select(attrs={
                "class": "form-select",
            }),
            "estado": forms.Select(attrs={
                "class": "form-select",
            }),
        }

    def clean(self):
        cleaned = super().clean()
        origen = cleaned.get("origen")
        proveedor = cleaned.get("proveedor")

        if origen == CompraVentaOperacion.ORIGEN_PROVEEDOR and not proveedor:
            raise forms.ValidationError(
                "Si el origen es PROVEEDOR, tenés que elegir un proveedor/agencia."
            )

        if origen != CompraVentaOperacion.ORIGEN_PROVEEDOR:
            cleaned["proveedor"] = None

        return cleaned


# ==========================================================
# 💰 PAGO A PROVEEDOR
# ==========================================================
class PagoProveedorForm(forms.ModelForm):
    class Meta:
        model = PagoProveedor
        fields = ["fecha", "monto", "nota"]
        widgets = {
            "fecha": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "monto": forms.NumberInput(attrs={
                "class": "form-control",
            }),
            "nota": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Observación opcional",
            }),
        }


# ==========================================================
# 💸 DEUDA (MONTO TOTAL)
# ==========================================================
class DeudaProveedorForm(forms.ModelForm):
    class Meta:
        model = DeudaProveedor
        fields = ["monto_total"]
        widgets = {
            "monto_total": forms.NumberInput(attrs={
                "class": "form-control",
            }),
        }

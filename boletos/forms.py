from django import forms
from decimal import Decimal
from datetime import date

from clientes.models import Cliente
from vehiculos.models import Vehiculo
from .models import BoletoCompraventa, Pagare


# ==========================================================
# BOLETO DE COMPRAVENTA
# ==========================================================
class CrearBoletoForm(forms.Form):

    MONEDAS = (
        ('ARS', 'Pesos ($)'),
        ('USD', 'Dólares (U$S)'),
    )

    moneda = forms.ChoiceField(
        label="Moneda",
        choices=MONEDAS,
        initial='ARS',
        widget=forms.Select(attrs={"class": "form-select", "id": "id_moneda"})
    )

    vehiculo = forms.ModelChoiceField(
        queryset=Vehiculo.objects.all(),
        label="Vehículo",
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_vehiculo"})
    )

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(activo=True),
        label="Cliente",
        required=True,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_cliente"})
    )

    # DATOS DEL VEHÍCULO (SOLO LECTURA)
    marca = forms.CharField(
        label="Marca", max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_marca", "readonly": "readonly"})
    )
    modelo = forms.CharField(
        label="Modelo", max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_modelo", "readonly": "readonly"})
    )
    anio = forms.CharField(
        label="Año", max_length=10, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_anio", "readonly": "readonly"})
    )
    motor = forms.CharField(
        label="Motor", max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_motor", "readonly": "readonly"})
    )
    chasis = forms.CharField(
        label="Chasis", max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_chasis", "readonly": "readonly"})
    )
    patente = forms.CharField(
        label="Dominio / Patente", max_length=20, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_patente", "readonly": "readonly"})
    )

    # DATOS ECONÓMICOS
    precio_total_unidad = forms.CharField(
        label="Precio total de la unidad", max_length=100, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    # DATOS DEL COMPRADOR
    comprador_texto = forms.CharField(
        label="Comprador (texto completo)", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_comprador_texto"})
    )
    domicilio_comprador = forms.CharField(
        label="Domicilio del comprador", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_domicilio_comprador"})
    )
    dni_comprador = forms.CharField(
        label="DNI comprador", max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_dni_comprador"})
    )

    # DATOS LEGALES
    compania_seguro = forms.CharField(
        label="Compañía de seguro", max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    domicilio_legal = forms.CharField(
        label="Domicilio legal (cláusula 7)", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_domicilio_legal"})
    )

    # CONDICIONES DE PAGO
    precio_letras = forms.CharField(
        label="Precio en letras", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    precio_numeros = forms.CharField(
        label="Precio en números", max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    saldo_forma_pago = forms.CharField(
        label="Saldo / forma de pago",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"})
    )

    # NOTA
    nota = forms.CharField(
        label="Nota", required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )

    # FIRMA
    apellido_comprador = forms.CharField(
        label="Apellido comprador", max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    nombre_comprador = forms.CharField(
        label="Nombre comprador", max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    direccion_firma = forms.CharField(
        label="Dirección comprador (firma)", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    def clean_cliente(self):
        cliente = self.cleaned_data.get("cliente")
        if not cliente:
            raise forms.ValidationError("Debe seleccionar un cliente.")
        if not cliente.activo:
            raise forms.ValidationError("El cliente seleccionado se encuentra inactivo.")
        return cliente

    def clean_vehiculo(self):
        return self.cleaned_data.get("vehiculo")


# ==========================================================
# BOLETO DE COMPRAVENTA – EDICIÓN
# ==========================================================
class EditarBoletoForm(forms.ModelForm):

    MONEDAS = (
        ('ARS', 'Pesos ($)'),
        ('USD', 'Dólares (U$S)'),
    )

    moneda = forms.ChoiceField(
        label="Moneda", choices=MONEDAS, initial='ARS',
        widget=forms.Select(attrs={"class": "form-select"})
    )
    precio_numeros = forms.CharField(
        label="Precio en números", max_length=100, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: $5.000.000"})
    )
    precio_letras = forms.CharField(
        label="Precio en letras", max_length=255, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: CINCO MILLONES DE PESOS"})
    )
    saldo_forma_pago = forms.CharField(
        label="Saldo / Forma de pago", required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": 3,
            "placeholder": "Ej: 12 cuotas de $300.000 con vencimiento el día 10 de cada mes",
        })
    )
    compania_seguro = forms.CharField(
        label="Compañía de seguro", max_length=100, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    domicilio_legal = forms.CharField(
        label="Domicilio legal (cláusula 7)", max_length=255, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = BoletoCompraventa
        fields = ["cliente", "vehiculo"]
        widgets = {
            "cliente":  forms.Select(attrs={"class": "form-select"}),
            "vehiculo": forms.Select(attrs={"class": "form-select"}),
        }


# ==========================================================
# PAGARÉ – CREACIÓN EN LOTE
# ==========================================================
class CrearPagareLoteForm(forms.Form):

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(activo=True),
        label="Cliente", required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    beneficiario = forms.CharField(
        label="Beneficiario", required=True, initial="AMICHETTI HUGO ALBERTO",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    monto_total = forms.DecimalField(
        label="Monto total", max_digits=14, decimal_places=2,
        required=True, min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    cantidad = forms.IntegerField(
        label="Cantidad de pagarés", min_value=1, max_value=60, required=True,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    lugar_emision = forms.CharField(
        label="Lugar de emisión", required=True, initial="Rojas",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    fecha_emision = forms.DateField(
        label="Fecha de emisión", required=True, initial=date.today,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    def clean_cliente(self):
        cliente = self.cleaned_data.get("cliente")
        if not cliente:
            raise forms.ValidationError("Debe seleccionar un cliente.")
        if not cliente.activo:
            raise forms.ValidationError("El cliente seleccionado está inactivo.")
        return cliente

    def clean_monto_total(self):
        monto = self.cleaned_data.get("monto_total") or Decimal("0")
        if monto <= 0:
            raise forms.ValidationError("El monto total debe ser mayor a 0.")
        return monto

    def clean(self):
        cleaned  = super().clean()
        monto    = cleaned.get("monto_total")
        cantidad = cleaned.get("cantidad")
        if monto and cantidad and cantidad > 0:
            if (monto / Decimal(cantidad)) < Decimal("0.01"):
                raise forms.ValidationError(
                    "El monto total es demasiado bajo para la cantidad de pagarés."
                )
        return cleaned


# ==========================================================
# PAGARÉ – EDICIÓN INDIVIDUAL
# ==========================================================
class EditarPagareForm(forms.ModelForm):

    class Meta:
        model = Pagare
        fields = ["monto", "fecha_vencimiento"]
        widgets = {
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "fecha_vencimiento": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return monto

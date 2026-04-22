from django import forms
from decimal import Decimal
from datetime import date

from clientes.models import Cliente
from vehiculos.models import Vehiculo
from .models import BoletoCompraventa, Pagare, Reserva, EntregaDocumentacion


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
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_motor"})
    )
    chasis = forms.CharField(
        label="Chasis", max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "id": "id_chasis"})
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
    motor = forms.CharField(
        label="N° Motor", max_length=100, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    chasis = forms.CharField(
        label="N° Chasis", max_length=100, required=False,
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
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"})
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
            "fecha_vencimiento": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return monto


# ==========================================================
# RESERVA DE VEHÍCULO
# ==========================================================
W = {"class": "form-control"}   # shortcut widget attrs
WS = {"class": "form-select"}


class ReservaForm(forms.ModelForm):

    class Meta:
        model = Reserva
        exclude = ["numero_reserva", "creado"]
        widgets = {
            # Solicitante
            "apellido_nombre": forms.TextInput(attrs={**W, "placeholder": "Apellido y Nombre o Razón Social"}),
            "dni":             forms.TextInput(attrs={**W, "placeholder": "DNI"}),
            "domicilio":       forms.TextInput(attrs={**W, "placeholder": "Domicilio"}),
            "telefono":        forms.TextInput(attrs={**W, "placeholder": "Teléfono"}),
            "cuit":            forms.TextInput(attrs={**W, "placeholder": "CUIT"}),
            "iva":             forms.TextInput(attrs={**W, "placeholder": "Condición IVA"}),
            # Vehículo
            "vehiculo": forms.Select(attrs={**WS}),
            "marca":    forms.TextInput(attrs={**W, "placeholder": "Marca"}),
            "modelo":   forms.TextInput(attrs={**W, "placeholder": "Modelo"}),
            "anio":     forms.TextInput(attrs={**W, "placeholder": "Año"}),
            "dominio":  forms.TextInput(attrs={**W, "placeholder": "Dominio / Patente"}),
            "motor_nro":  forms.TextInput(attrs={**W, "placeholder": "N° Motor"}),
            "chasis_nro": forms.TextInput(attrs={**W, "placeholder": "N° Chasis"}),
            # Detalle operación
            "precio_vehiculo": forms.NumberInput(attrs={**W, "step": "0.01"}),
            "opcionales":      forms.NumberInput(attrs={**W, "step": "0.01"}),
            "total_a_pagar":   forms.NumberInput(attrs={**W, "step": "0.01"}),
            "senia":           forms.NumberInput(attrs={**W, "step": "0.01"}),
            # Propuesta pago
            "contado_efectivo":  forms.NumberInput(attrs={**W, "step": "0.01"}),
            "pago_entrega":      forms.NumberInput(attrs={**W, "step": "0.01"}),
            "cheques":           forms.Textarea(attrs={**W, "rows": 2}),
            "total_propuesta":   forms.NumberInput(attrs={**W, "step": "0.01"}),
            "credito_prendario": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "otro_concepto":     forms.TextInput(attrs={**W}),
            "cant_cuotas":       forms.NumberInput(attrs={**W}),
            "valor_cuota":       forms.NumberInput(attrs={**W, "step": "0.01"}),
            "dia_cuota":         forms.TextInput(attrs={**W, "placeholder": "Ej: 10"}),
            # Permuta
            "permuta_marca":   forms.TextInput(attrs={**W}),
            "permuta_patente": forms.TextInput(attrs={**W}),
            "permuta_suma":    forms.NumberInput(attrs={**W, "step": "0.01"}),
            "permuta_total":   forms.NumberInput(attrs={**W, "step": "0.01"}),
            # Otros
            "observaciones": forms.Textarea(attrs={**W, "rows": 3}),
            "fecha_reserva": forms.DateInput(format="%Y-%m-%d", attrs={**W, "type": "date"}),
        }


# ==========================================================
# ENTREGA DE DOCUMENTACION
# ==========================================================
class EntregaDocumentacionForm(forms.ModelForm):
    class Meta:
        model = EntregaDocumentacion
        fields = [
            "vehiculo",
            "marca", "modelo", "dominio", "anio", "motor", "chasis",
            "nombre_comprador", "dni_comprador", "domicilio_comprador", "telefono_comprador",
            "titulo", "cedula", "cedula_azul",
            "formulario_08", "formulario_02", "formulario_12", "formulario_13d",
            "gp01", "gnc", "vtv", "verificacion_policial",
            "informe_dominio", "infracciones", "patentes_al_dia", "libre_deuda",
            "manuales", "codigo_radio", "llave_duplicado",
            "rueda_auxilio", "gato_llave_rueda",
            "observaciones", "fecha", "hora",
        ]
        widgets = {
            "vehiculo": forms.Select(attrs={"class": "form-select", "id": "id_vehiculo_select"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "dominio": forms.TextInput(attrs={"class": "form-control"}),
            "anio": forms.TextInput(attrs={"class": "form-control"}),
            "motor": forms.TextInput(attrs={"class": "form-control"}),
            "chasis": forms.TextInput(attrs={"class": "form-control"}),
            "nombre_comprador": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre y apellido"}),
            "dni_comprador": forms.TextInput(attrs={"class": "form-control", "placeholder": "DNI"}),
            "domicilio_comprador": forms.TextInput(attrs={"class": "form-control", "placeholder": "Domicilio"}),
            "telefono_comprador": forms.TextInput(attrs={"class": "form-control", "placeholder": "Telefono"}),
            "titulo": forms.Select(attrs={"class": "form-select"}),
            "cedula": forms.Select(attrs={"class": "form-select"}),
            "cedula_azul": forms.Select(attrs={"class": "form-select"}),
            "formulario_08": forms.Select(attrs={"class": "form-select"}),
            "formulario_02": forms.Select(attrs={"class": "form-select"}),
            "formulario_12": forms.Select(attrs={"class": "form-select"}),
            "formulario_13d": forms.Select(attrs={"class": "form-select"}),
            "gp01": forms.Select(attrs={"class": "form-select"}),
            "gnc": forms.Select(attrs={"class": "form-select"}),
            "vtv": forms.Select(attrs={"class": "form-select"}),
            "verificacion_policial": forms.Select(attrs={"class": "form-select"}),
            "informe_dominio": forms.Select(attrs={"class": "form-select"}),
            "infracciones": forms.Select(attrs={"class": "form-select"}),
            "patentes_al_dia": forms.Select(attrs={"class": "form-select"}),
            "libre_deuda": forms.Select(attrs={"class": "form-select"}),
            "manuales": forms.Select(attrs={"class": "form-select"}),
            "codigo_radio": forms.Select(attrs={"class": "form-select"}),
            "llave_duplicado": forms.Select(attrs={"class": "form-select"}),
            "rueda_auxilio": forms.Select(attrs={"class": "form-select"}),
            "gato_llave_rueda": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "hora": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehiculo"].required = False
        self.fields["vehiculo"].queryset = Vehiculo.objects.all().order_by("-id")

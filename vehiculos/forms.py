from django import forms
from .models import Vehiculo, FichaVehicular


# ==========================================================
# FORMULARIO BÁSICO PARA AGREGAR VEHÍCULO
# ==========================================================
class VehiculoBasicoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = [
            'marca',
            'modelo',
            'dominio',
            'anio',
            'kilometros',
            'precio',
            'estado',
            'numero_carpeta',
        ]

        labels = {
            'marca': 'Marca',
            'modelo': 'Modelo',
            'dominio': 'Dominio',
            'anio': 'Año',
            'kilometros': 'Kilometraje',
            'precio': 'Precio',
            'estado': 'Estado',
            'numero_carpeta': 'Número de carpeta',
        }

        widgets = {
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'dominio': forms.TextInput(attrs={'class': 'form-control'}),
            'anio': forms.NumberInput(attrs={'class': 'form-control'}),
            'kilometros': forms.NumberInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'numero_carpeta': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ej: C-2025-014'
                }
            ),
        }


# ==========================================================
# FORMULARIO PARA EDITAR VEHÍCULO
# ==========================================================
class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = [
            'marca',
            'modelo',
            'anio',
            'kilometros',
            'dominio',
            'estado',
            'numero_carpeta',
        ]

        labels = {
            'marca': 'Marca',
            'modelo': 'Modelo',
            'anio': 'Año',
            'kilometros': 'Kilometraje',
            'dominio': 'Dominio',
            'estado': 'Estado',
            'numero_carpeta': 'Número de carpeta',
        }

        widgets = {
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'anio': forms.NumberInput(attrs={'class': 'form-control'}),
            'kilometros': forms.NumberInput(attrs={'class': 'form-control'}),
            'dominio': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'numero_carpeta': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ej: C-2025-014'
                }
            ),
        }


# ==========================================================
# FORMULARIO COMPLETO PARA FICHA VEHICULAR
# ==========================================================
class FichaVehicularForm(forms.ModelForm):
    class Meta:
        model = FichaVehicular

        # ⛔ motor y chasis no se usan en UI
        exclude = [
            'vehiculo',
            'total_gastos',
            'motor',
            'chasis',
        ]

        labels = {
            # ================= DATOS BÁSICOS =================
            'numero_motor': 'Número motor',
            'numero_chasis': 'Número chasis',
            'fecha_inscripcion_inicial': 'Fecha inscripción inicial',
            'color': 'Color',
            'combustible': 'Combustible',
            'transmision': 'Transmisión',

            # ================= TITULARIDAD =================
            'vendedor': 'Vendedor',
            'contacto': 'Contacto',
            'email_contacto': 'Email contacto',
            'titular': 'Titular',
            'domicilio_titular': 'Domicilio titular',
            'dni_titular': 'DNI titular',
            'estado_civil': 'Estado civil',
            'cuit_cuil_dni': 'CUIT / CUIL / DNI',
            'tipo_ingreso': 'Tipo ingreso',
            'numero_consignacion_factura': 'N° consignación / factura',

            # ================= DOCUMENTACIÓN =================
            'patentes_estado': 'Estado patentes',
            'patentes_monto': 'Monto deuda',
            'patentes_vto1': 'Vencimiento 1',
            'patentes_vto2': 'Vencimiento 2',
            'patentes_vto3': 'Vencimiento 3',
            'patentes_vto4': 'Vencimiento 4',
            'patentes_vto5': 'Vencimiento 5',

            'f08_estado': 'Formulario 08',
            'cedula_estado': 'Cédula',

            'verificacion_estado': 'Verificación policial',
            'verificacion_vencimiento': 'Vencimiento verificación',

            'autopartes_estado': 'Grabado autopartes',
            'autopartes_turno': 'Turno grabado autopartes',
            'autopartes_turno_obs': 'Observaciones turno grabado autopartes',

            'vtv_estado': 'VTV',
            'vtv_turno': 'Turno VTV',
            'vtv_vencimiento': 'Vencimiento VTV',

            # ================= CHECKLIST =================
            'duplicado_llave_estado': 'Duplicado de llave',
            'duplicado_llave_obs': 'Observación',

            'codigo_llave_estado': 'Código de llave',
            'codigo_llave_obs': 'Observación',

            'codigo_radio_estado': 'Código de radio',
            'codigo_radio_obs': 'Observación',

            'manuales_estado': 'Manuales',
            'manuales_obs': 'Observación',

            'oblea_gnc_estado': 'Oblea GNC',
            'oblea_gnc_obs': 'Observación',

            # ================= GASTOS =================
            'gasto_f08': 'Gasto Formulario 08',
            'gasto_informes': 'Gasto informes',
            'gasto_patentes': 'Gasto patentes',
            'gasto_verificacion': 'Gasto verificación',
            'gasto_autopartes': 'Gasto autopartes',
            'gasto_vtv': 'Gasto VTV',
            'gasto_r541': 'Gasto R-541',
            'gasto_firmas': 'Gasto firmas',

            # ================= OBSERVACIONES =================
            'observaciones': 'Observaciones',
        }

        widgets = {

            # ================= DATOS BÁSICOS =================
            'numero_motor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_chasis': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_inscripcion_inicial': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'combustible': forms.TextInput(attrs={'class': 'form-control'}),
            'transmision': forms.TextInput(attrs={'class': 'form-control'}),

            # ================= TITULARIDAD =================
            'vendedor': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}),
            'titular': forms.TextInput(attrs={'class': 'form-control'}),
            'domicilio_titular': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_titular': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit_cuil_dni': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_ingreso': forms.Select(attrs={'class': 'form-control'}),
            'numero_consignacion_factura': forms.TextInput(attrs={'class': 'form-control'}),

            # ================= DOCUMENTACIÓN =================
            'patentes_estado': forms.Select(attrs={'class': 'form-control'}),
            'patentes_monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'patentes_vto1': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'patentes_vto2': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'patentes_vto3': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'patentes_vto4': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'patentes_vto5': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),

            'f08_estado': forms.Select(attrs={'class': 'form-control'}),
            'cedula_estado': forms.Select(attrs={'class': 'form-control'}),

            'verificacion_estado': forms.Select(attrs={'class': 'form-control'}),
            'verificacion_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),

            'autopartes_estado': forms.Select(attrs={'class': 'form-control'}),
            'autopartes_turno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'autopartes_turno_obs': forms.TextInput(attrs={'class': 'form-control'}),

            'vtv_estado': forms.Select(attrs={'class': 'form-control'}),
            'vtv_turno': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'vtv_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),

            # ================= CHECKLIST =================
            'duplicado_llave_estado': forms.RadioSelect(choices=[('si', 'Sí'), ('no', 'No')]),
            'duplicado_llave_obs': forms.TextInput(attrs={'class': 'form-control'}),

            'codigo_llave_estado': forms.RadioSelect(choices=[('si', 'Sí'), ('no', 'No')]),
            'codigo_llave_obs': forms.TextInput(attrs={'class': 'form-control'}),

            'codigo_radio_estado': forms.RadioSelect(choices=[('si', 'Sí'), ('no', 'No')]),
            'codigo_radio_obs': forms.TextInput(attrs={'class': 'form-control'}),

            'manuales_estado': forms.RadioSelect(choices=[('si', 'Sí'), ('no', 'No')]),
            'manuales_obs': forms.TextInput(attrs={'class': 'form-control'}),

            'oblea_gnc_estado': forms.RadioSelect(choices=[('si', 'Sí'), ('no', 'No')]),
            'oblea_gnc_obs': forms.TextInput(attrs={'class': 'form-control'}),

            # ================= GASTOS =================
            'gasto_f08': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_informes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_patentes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_verificacion': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_autopartes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_vtv': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_r541': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_firmas': forms.NumberInput(attrs={'class': 'form-control'}),

            # ================= OBSERVACIONES =================
            'observaciones': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
        }

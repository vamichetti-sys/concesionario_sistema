from django import forms
from .models import Vehiculo, FichaVehicular, FichaTecnica
from django.conf import settings


# ==========================================================
# FORMULARIO BÁSICO PARA AGREGAR VEHÍCULO
# ==========================================================
class VehiculoBasicoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = [
            'unidad', 
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
            'unidad': 'Unidad',
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
            'unidad': forms.Select(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'dominio': forms.TextInput(attrs={'class': 'form-control'}),
            'anio': forms.NumberInput(attrs={'class': 'form-control'}),
            'kilometros': forms.NumberInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'numero_carpeta': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: C-2025-014'}
            ),
        }


# ==========================================================
# FORMULARIO PARA EDITAR VEHÍCULO
# ==========================================================
class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = [
            'unidad',
            'marca',
            'modelo',
            'anio',
            'kilometros',
            'dominio',
            'precio',
            'estado',
            'numero_carpeta',
        ]

        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'anio': forms.NumberInput(attrs={'class': 'form-control'}),
            'kilometros': forms.NumberInput(attrs={'class': 'form-control'}),
            'dominio': forms.TextInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'numero_carpeta': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ==========================================================
# FORMULARIO COMPLETO PARA FICHA VEHICULAR
# ==========================================================
class FichaVehicularForm(forms.ModelForm):

    # ======================================================
    # 🔑 DEFINICIÓN EXPLÍCITA DE FECHAS (FIX DEFINITIVO)
    # ======================================================
    fecha_inscripcion_inicial = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    patentes_vto1 = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )
    patentes_vto2 = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )
    patentes_vto3 = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )
    patentes_vto4 = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )
    patentes_vto5 = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    verificacion_vencimiento = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    autopartes_turno = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    vtv_turno = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    vtv_vencimiento = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    # =========================
    # TURNOS ADICIONALES
    # =========================
    verificacion_turno = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    gnc_turno = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        )
    )

    class Meta:
        model = FichaVehicular
        fields = [
            'numero_motor',
            'numero_chasis',
            'fecha_inscripcion_inicial',

            'color',
            'combustible',
            'transmision',

            'vendedor',
            'contacto',
            'email_contacto',

            'titular',
            'domicilio_titular',
            'dni_titular',
            'estado_civil',
            'cuit_cuil_dni',

            'tipo_ingreso',
            'numero_consignacion_factura',

            'patentes_estado',
            'patentes_monto',
            'patentes_vto1',
            'patentes_vto2',
            'patentes_vto3',
            'patentes_vto4',
            'patentes_vto5',

            'f08_estado',
            'cedula_estado',

            'verificacion_estado',
            'verificacion_vencimiento',
            'verificacion_turno',

            'autopartes_estado',
            'autopartes_turno',

            'vtv_estado',
            'vtv_turno',
            'vtv_vencimiento',

            'gnc_turno',

            'duplicado_llave_estado',
            'duplicado_llave_obs',
            'codigo_llave_estado',
            'codigo_llave_obs',
            'codigo_radio_estado',
            'codigo_radio_obs',
            'manuales_estado',
            'manuales_obs',
            'oblea_gnc_estado',
            'oblea_gnc_obs',

            'gasto_f08',
            'gasto_informes',
            'gasto_patentes',
            'gasto_infracciones',
            'gasto_verificacion',
            'gasto_autopartes',
            'gasto_vtv',
            'gasto_r541',
            'gasto_firmas',

            'observaciones',
        ]

        labels = {
            'numero_motor': 'Número motor',
            'numero_chasis': 'Número chasis',
            'fecha_inscripcion_inicial': 'Fecha inscripción inicial',
            'color': 'Color',
            'combustible': 'Combustible',
            'transmision': 'Transmisión',
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
            'verificacion_turno': 'Turno verificación policial',
            'autopartes_estado': 'Grabado autopartes',
            'autopartes_turno': 'Turno grabado autopartes',
            'vtv_estado': 'VTV',
            'vtv_turno': 'Turno VTV',
            'vtv_vencimiento': 'Vencimiento VTV',
            'gnc_turno': 'Turno GNC',
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
            'gasto_f08': 'Gasto Formulario 08',
            'gasto_informes': 'Gasto informes',
            'gasto_patentes': 'Gasto patentes',
            'gasto_infracciones': 'Gasto infracciones',
            'gasto_verificacion': 'Gasto verificación',
            'gasto_autopartes': 'Gasto autopartes',
            'gasto_vtv': 'Gasto VTV',
            'gasto_r541': 'Gasto R-541',
            'gasto_firmas': 'Gasto firmas',
            'observaciones': 'Observaciones',
        }

        widgets = {
            'numero_motor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_chasis': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'combustible': forms.TextInput(attrs={'class': 'form-control'}),
            'transmision': forms.TextInput(attrs={'class': 'form-control'}),
            'vendedor': forms.Select(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}),
            'titular': forms.TextInput(attrs={'class': 'form-control'}),
            'domicilio_titular': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_titular': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit_cuil_dni': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_consignacion_factura': forms.TextInput(attrs={'class': 'form-control'}),
            'patentes_monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_f08': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_informes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_patentes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_infracciones': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_verificacion': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_autopartes': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_vtv': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_r541': forms.NumberInput(attrs={'class': 'form-control'}),
            'gasto_firmas': forms.NumberInput(attrs={'class': 'form-control'}),
            'patentes_estado': forms.Select(attrs={'class': 'form-control'}),
            'f08_estado': forms.Select(attrs={'class': 'form-control'}),
            'cedula_estado': forms.Select(attrs={'class': 'form-control'}),
            'verificacion_estado': forms.Select(attrs={'class': 'form-control'}),
            'autopartes_estado': forms.Select(attrs={'class': 'form-control'}),
            'vtv_estado': forms.Select(attrs={'class': 'form-control'}),
            'tipo_ingreso': forms.Select(attrs={'class': 'form-control'}),
            'duplicado_llave_estado': forms.Select(attrs={'class': 'form-control'}),
            'codigo_llave_estado': forms.Select(attrs={'class': 'form-control'}),
            'codigo_radio_estado': forms.Select(attrs={'class': 'form-control'}),
            'manuales_estado': forms.Select(attrs={'class': 'form-control'}),
            'oblea_gnc_estado': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'oblea_gnc_obs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'duplicado_llave_obs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    # ======================================================
    # INIT (SE CONSERVA)
    # ======================================================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# ==========================================================
# FORMULARIO FICHA TÉCNICA
# ==========================================================
class FichaTecnicaForm(forms.ModelForm):
    class Meta:
        model = FichaTecnica
        exclude = ['vehiculo']

        widgets = {
            'tipo_vehiculo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sedán, SUV, Pick Up...'}),
            'potencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 150 HP'}),
            'cilindrada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.6 / 2.0T'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Hidráulica, Eléctrica'}),
            'capacidad_tanque': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 55'}),
            'capacidad_baul': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 420'}),
            'puertas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 4'}),
            'largo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 4.50'}),
            'ancho': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.86'}),
            'alto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.50'}),
            'peso': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1350'}),
            'abs_frenos': forms.Select(attrs={'class': 'form-control'}),
            'airbag': forms.Select(attrs={'class': 'form-control'}),
            'airbags_laterales': forms.Select(attrs={'class': 'form-control'}),
            'aire_acondicionado': forms.Select(attrs={'class': 'form-control'}),
            'cierre_centralizado': forms.Select(attrs={'class': 'form-control'}),
            'alzacristales': forms.Select(attrs={'class': 'form-control'}),
            'alarma': forms.Select(attrs={'class': 'form-control'}),
            'sensor_estacionamiento': forms.Select(attrs={'class': 'form-control'}),
            'camara_retroceso': forms.Select(attrs={'class': 'form-control'}),
            'pantalla': forms.Select(attrs={'class': 'form-control'}),
            'gps': forms.Select(attrs={'class': 'form-control'}),
            'isofix': forms.Select(attrs={'class': 'form-control'}),
            'techo_solar': forms.Select(attrs={'class': 'form-control'}),
            'llantas_aleacion': forms.Select(attrs={'class': 'form-control'}),
            'control_crucero': forms.Select(attrs={'class': 'form-control'}),
            'control_traccion': forms.Select(attrs={'class': 'form-control'}),
            'asientos_cuero': forms.Select(attrs={'class': 'form-control'}),
            'bluetooth': forms.Select(attrs={'class': 'form-control'}),
            'est_neumaticos': forms.Select(attrs={'class': 'form-control'}),
            'est_frenos': forms.Select(attrs={'class': 'form-control'}),
            'est_amortiguadores': forms.Select(attrs={'class': 'form-control'}),
            'est_bateria': forms.Select(attrs={'class': 'form-control'}),
            'est_escape': forms.Select(attrs={'class': 'form-control'}),
            'est_chapa_pintura': forms.Select(attrs={'class': 'form-control'}),
            'est_tapizado': forms.Select(attrs={'class': 'form-control'}),
            'est_vidrios': forms.Select(attrs={'class': 'form-control'}),
            'est_luces': forms.Select(attrs={'class': 'form-control'}),
            'est_motor': forms.Select(attrs={'class': 'form-control'}),
            'observaciones_tecnicas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalles adicionales, trabajos realizados...'}),
        }
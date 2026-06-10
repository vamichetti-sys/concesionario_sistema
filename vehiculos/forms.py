from django import forms
from .models import Vehiculo, FichaVehicular, FichaTecnica
from django.conf import settings


# ==========================================================
# MIXIN: número de carpeta único entre vehículos ACTIVOS
# (en stock, temporal o reventa). Los vendidos pueden repetir.
# ==========================================================
class CarpetaUnicaMixin:
    def clean_numero_carpeta(self):
        valor = (self.cleaned_data.get("numero_carpeta") or "").strip()
        estado = self.cleaned_data.get("estado") or getattr(self.instance, "estado", "")
        # Si no hay número, o el vehículo es vendido, no se valida.
        if not valor or estado == "vendido":
            return valor
        qs = Vehiculo.objects.filter(numero_carpeta=valor).exclude(estado="vendido")
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        otro = qs.first()
        if otro:
            raise forms.ValidationError(
                f"El número de carpeta «{valor}» ya está en uso por "
                f"{otro.marca} {otro.modelo} ({otro.dominio}). Usá otro número."
            )
        return valor

    def clean_dominio(self):
        valor = (self.cleaned_data.get("dominio") or "").strip().upper()
        # Vehículo 0km / sin patente: se permite "A DECLARAR" (varios pueden
        # tenerlo) sin chequear unicidad.
        if valor in ("", "A DECLARAR", "ADECLARAR", "A DECLARAR.", "ADECLAR"):
            return "A DECLARAR" if valor else valor
        # Patente real: única entre vehículos activos (los vendidos no cuentan).
        qs = Vehiculo.objects.filter(dominio__iexact=valor).exclude(estado="vendido")
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        otro = qs.first()
        if otro:
            raise forms.ValidationError(
                f"El dominio «{valor}» ya está en otro vehículo activo "
                f"({otro.marca} {otro.modelo}). Usá «A DECLARAR» si es 0km."
            )
        return valor


# ==========================================================
# FORMULARIO BÁSICO PARA AGREGAR VEHÍCULO
# ==========================================================
class VehiculoBasicoForm(CarpetaUnicaMixin, forms.ModelForm):
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
            'fecha_ingreso',
            'es_0km',
        ]

        labels = {
            'unidad': 'Perteneciente a',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'dominio': 'Dominio',
            'anio': 'Año',
            'kilometros': 'Kilometraje',
            'precio': 'Precio',
            'estado': 'Estado',
            'numero_carpeta': 'Número de carpeta',
            'fecha_ingreso': 'Fecha de ingreso',
            'es_0km': '¿Es 0km?',
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
            'fecha_ingreso': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'
            ),
            'es_0km': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ==========================================================
# FORMULARIO PARA EDITAR VEHÍCULO
# ==========================================================
class VehiculoForm(CarpetaUnicaMixin, forms.ModelForm):
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
            'fecha_ingreso',
            'es_0km',
        ]

        labels = {
            'fecha_ingreso': 'Fecha de ingreso',
            'es_0km': '¿Es 0km?',
        }

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
            'fecha_ingreso': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'
            ),
            'es_0km': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
            'patentes_adeuda',
            'patentes_monto',
            'patente_mensual',
            'patentes_vto1',
            'patentes_vto2',
            'patentes_vto3',
            'patentes_vto4',
            'patentes_vto5',

            'f08_estado',
            'cedula_estado',
            'informe',
            'radicacion_anterior',

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
            'informe': 'Informe',
            'radicacion_anterior': 'Radicación anterior',
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
            'patentes_adeuda': forms.Select(attrs={'class': 'form-control'}),
            'patente_mensual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'f08_estado': forms.Select(attrs={'class': 'form-control'}),
            'cedula_estado': forms.Select(attrs={'class': 'form-control'}),
            'informe': forms.Select(attrs={'class': 'form-control'}),
            'radicacion_anterior': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: CABA, La Plata, Rojas...'}),
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

        # ▸ Estilos comunes para que se vea consistente y los textareas
        #   sean grandes, claros y bien visibles (a pedido).
        _OBS_CLS = 'form-control ficha-obs'
        _SELECT_CLS = 'form-select'
        _INPUT_CLS = 'form-control'

        widgets = {
            # ── Mantenimiento ───────────────────────────────
            'ultimo_service_fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': _INPUT_CLS, 'type': 'date'}),
            'ultimo_service_km': forms.NumberInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Km'}),
            'ultimo_cambio_aceite_fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': _INPUT_CLS, 'type': 'date'}),
            'ultimo_cambio_aceite_km': forms.NumberInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Km'}),
            'ultimo_cambio_correa_fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': _INPUT_CLS, 'type': 'date'}),
            'ultimo_cambio_correa_km': forms.NumberInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Km'}),

            # ── Historia / Estado ──────────────────────────
            'repintado': forms.Select(attrs={'class': _SELECT_CLS}),
            'partes_repintadas': forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Ej: paragolpes delantero, puerta derecha...'}),
            'chocado': forms.Select(attrs={'class': _SELECT_CLS}),
            'detalles_choque': forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 3, 'placeholder': 'Cuándo, dónde, qué se reparó...'}),
            'detalles_estado': forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 3, 'placeholder': 'Rayones, golpes leves, particularidades...'}),
            'no_funciona': forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 3, 'placeholder': 'Aire que no enfría, alguna luz fundida, etc.'}),

            # ── Cubiertas ──────────────────────────────────
            'cubierta_di': forms.Select(attrs={'class': _SELECT_CLS, 'data-tire': 'DI'}),
            'cubierta_dd': forms.Select(attrs={'class': _SELECT_CLS, 'data-tire': 'DD'}),
            'cubierta_ti': forms.Select(attrs={'class': _SELECT_CLS, 'data-tire': 'TI'}),
            'cubierta_td': forms.Select(attrs={'class': _SELECT_CLS, 'data-tire': 'TD'}),
            'cubierta_auxilio': forms.Select(attrs={'class': _SELECT_CLS, 'data-tire': 'AX'}),
            'cubiertas_obs': forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 3, 'placeholder': 'Observaciones sobre cubiertas o rueda de auxilio...'}),

            # ── Estado sistemas ────────────────────────────
            'estado_motor':           forms.Select(attrs={'class': _SELECT_CLS}),
            'perdida_fluidos':        forms.Select(attrs={'class': _SELECT_CLS}),
            'perdida_fluidos_obs':    forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Aceite, refrigerante, etc.'}),
            'estado_suspension':      forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_frenos':          forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_electrico':       forms.Select(attrs={'class': _SELECT_CLS}),
            'fallas_electrico_obs':   forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Detalles de fallas eléctricas'}),
            'estado_faros_opticas':   forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_tapizados':       forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_volante':         forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_vidrios':         forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_calefaccion':     forms.Select(attrs={'class': _SELECT_CLS}),
            'estado_aire':            forms.Select(attrs={'class': _SELECT_CLS}),

            # ── Granizo ────────────────────────────────────
            'granizo_estado': forms.Select(attrs={'class': _SELECT_CLS}),
            'granizo_obs':    forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 3, 'placeholder': 'Zonas afectadas (capot, techo, baúl...)'}),

            # ── Observaciones generales ────────────────────
            'observaciones_tecnicas': forms.Textarea(attrs={'class': _OBS_CLS, 'rows': 4, 'placeholder': 'Detalles adicionales, trabajos realizados...'}),
        }
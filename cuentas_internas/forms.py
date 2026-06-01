from django import forms
from .models import CuentaInterna, MovimientoInterno, Alquiler, PagoAlquiler


class CuentaInternaForm(forms.ModelForm):
    class Meta:
        model = CuentaInterna
        fields = ['nombre', 'cargo', 'telefono', 'observaciones', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MovimientoInternoForm(forms.ModelForm):
    class Meta:
        model = MovimientoInterno
        fields = ['tipo', 'monto', 'concepto', 'fecha', 'observaciones']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'concepto': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AlquilerForm(forms.ModelForm):
    class Meta:
        model = Alquiler
        fields = ['nombre', 'direccion', 'arrendatario', 'telefono',
                  'monto_mensual', 'dia_pago', 'aumento_porcentaje', 'aumento_cada_meses',
                  'fecha_inicio', 'fecha_fin',
                  'contrato', 'observaciones', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Local centro'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'arrendatario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quién lo alquila'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'monto_mensual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'dia_pago': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '31'}),
            'aumento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'aumento_cada_meses': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Ej: 3'}),
            'fecha_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'contrato': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,image/*'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PagoAlquilerForm(forms.ModelForm):
    MESES = [(i, m) for i, m in enumerate(
        ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]) if i]

    periodo_mes = forms.TypedChoiceField(
        label='Mes del período', choices=MESES, coerce=int,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = PagoAlquiler
        fields = ['fecha', 'periodo_mes', 'periodo_anio', 'monto', 'forma_pago', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'periodo_anio': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Año'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'forma_pago': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
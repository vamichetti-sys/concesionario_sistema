from django import forms
from .models import CuentaInterna, MovimientoInterno


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
            'monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'concepto': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
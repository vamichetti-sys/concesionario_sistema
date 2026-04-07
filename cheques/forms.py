from django import forms
from .models import Cheque


class ChequeForm(forms.ModelForm):
    class Meta:
        model = Cheque
        fields = [
            'fecha_ingreso', 'cliente', 'nro_factura',
            'banco_emision', 'numero_cheque', 'titular_cheque', 'monto', 'fecha_deposito',
            'estado', 'depositado_en', 'fecha_endoso', 'destinatario_endoso',
            'observaciones'
        ]
        widgets = {
            'fecha_ingreso': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'nro_factura': forms.TextInput(attrs={'class': 'form-control'}),
            'banco_emision': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_cheque': forms.TextInput(attrs={'class': 'form-control'}),
            'titular_cheque': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha_deposito': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'depositado_en': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_endoso': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'destinatario_endoso': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
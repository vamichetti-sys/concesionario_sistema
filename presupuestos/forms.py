from django import forms
from .models import Presupuesto
from vehiculos.models import Vehiculo
from clientes.models import Cliente


class PresupuestoForm(forms.ModelForm):
    class Meta:
        model = Presupuesto
        fields = [
            'nombre_cliente', 'telefono_cliente', 'email_cliente', 'cliente',
            'vehiculo', 'precio_lista', 'descuento_porcentaje', 'precio_final', 'moneda',
            'forma_pago', 'anticipo', 'cantidad_cuotas', 'monto_cuota', 'interes_descripcion',
            'toma_usado', 'usado_descripcion', 'usado_valor',
            'gastos_transferencia', 'otros_gastos', 'gastos_descripcion',
            'observaciones', 'validez_dias', 'estado',
        ]
        widgets = {
            'nombre_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'email_cliente': forms.EmailInput(attrs={'class': 'form-control'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'vehiculo': forms.Select(attrs={'class': 'form-select'}),
            'precio_lista': forms.NumberInput(attrs={'class': 'form-control'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_final': forms.NumberInput(attrs={'class': 'form-control'}),
            'moneda': forms.Select(attrs={'class': 'form-select'}),
            'forma_pago': forms.Select(attrs={'class': 'form-select'}),
            'anticipo': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_cuotas': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'monto_cuota': forms.NumberInput(attrs={'class': 'form-control'}),
            'interes_descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: TNA 45%'}),
            'toma_usado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usado_descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ford Ka 2018'}),
            'usado_valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'gastos_transferencia': forms.NumberInput(attrs={'class': 'form-control'}),
            'otros_gastos': forms.NumberInput(attrs={'class': 'form-control'}),
            'gastos_descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'validez_dias': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehiculo'].queryset = Vehiculo.objects.filter(estado='stock')
        self.fields['cliente'].queryset = Cliente.objects.all()
        self.fields['cliente'].required = False
from django import forms
from django.forms import modelformset_factory
from decimal import Decimal

from .models import (
    PlanPago,
    CuotaPlan,
    Pago
)


# ==========================================================
# PLAN DE PAGO (NO SE TOCA)
# ==========================================================
class PlanPagoForm(forms.ModelForm):
    class Meta:
        model = PlanPago
        fields = [
            'descripcion',

            # 🔹 Definición del acuerdo
            'tipo_plan',
            'monto_financiado',
            'moneda',

            # 🔹 Anticipo
            'anticipo',

            # 🔹 Cuotas / vencimientos
            'cantidad_cuotas',
            'monto_cuota',
            'fecha_inicio',

            # 🔹 Intereses
            'interes_mora_mensual',
            'interes_descripcion',
        ]

        widgets = {
            'descripcion': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'tipo_plan': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'monto_financiado': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),

            'moneda': forms.Select(
                attrs={'class': 'form-select'}
            ),

            'anticipo': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),

            'cantidad_cuotas': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),

            'monto_cuota': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),

            'fecha_inicio': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),

            'interes_mora_mensual': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),

            'interes_descripcion': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2,
                    'placeholder': 'Ej: 5% mensual a partir del vencimiento'
                }
            ),
        }

    # ======================================================
    # VALIDACIONES DE NEGOCIO (NO ROMPEN NADA)
    # ======================================================
    def clean(self):
        cleaned_data = super().clean()

        tipo_plan = cleaned_data.get('tipo_plan')
        monto_financiado = cleaned_data.get('monto_financiado') or Decimal('0')
        anticipo = cleaned_data.get('anticipo') or Decimal('0')
        cantidad_cuotas = cleaned_data.get('cantidad_cuotas')

        # ------------------------------
        # Validaciones generales
        # ------------------------------
        if monto_financiado <= 0:
            self.add_error(
                'monto_financiado',
                'El monto financiado debe ser mayor a cero.'
            )

        if anticipo < 0:
            self.add_error(
                'anticipo',
                'El anticipo no puede ser negativo.'
            )

        if anticipo > monto_financiado:
            self.add_error(
                'anticipo',
                'El anticipo no puede ser mayor al monto financiado.'
            )

        # ------------------------------
        # Validaciones por tipo de plan
        # ------------------------------
        if tipo_plan == 'cuotas':
            if not cantidad_cuotas or cantidad_cuotas <= 0:
                self.add_error(
                    'cantidad_cuotas',
                    'Debe indicar la cantidad de cuotas.'
                )

        elif tipo_plan == 'unico':
            cleaned_data['cantidad_cuotas'] = 1

        elif tipo_plan == 'cheques':
            cleaned_data['cantidad_cuotas'] = 0
            cleaned_data['monto_cuota'] = Decimal('0')

        return cleaned_data


# ==========================================================
# 🆕 FORMSET PARA EDITAR FECHAS DE CUOTAS (AL CREAR PLAN)
# ==========================================================
CuotaFechaFormSet = modelformset_factory(
    CuotaPlan,
    fields=('vencimiento',),
    extra=0,
    widgets={
        'vencimiento': forms.DateInput(
            attrs={
                'type': 'date',
                'class': 'form-control'
            }
        )
    }
)


# ==========================================================
# FORMULARIO EDITAR CUOTA (POSTERIOR)
# ==========================================================
class EditarCuotaForm(forms.ModelForm):
    class Meta:
        model = CuotaPlan
        fields = ['vencimiento']
        widgets = {
            'vencimiento': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            )
        }

    def clean_vencimiento(self):
        if self.instance.estado == 'pagada':
            raise forms.ValidationError(
                "No se puede modificar la fecha de una cuota ya pagada."
            )
        return self.cleaned_data['vencimiento']


# ==========================================================
# FORMULARIO DE PAGO (PARA MODAL)
# ==========================================================
class PagoForm(forms.Form):
    cuota = forms.ModelChoiceField(
        queryset=CuotaPlan.objects.none(),
        label="Cuota a pagar",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    forma_pago = forms.ChoiceField(
        choices=Pago.FORMAS_PAGO,
        label="Forma de pago",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    monto = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        label="Monto abonado",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    banco = forms.CharField(
        required=False,
        label="Banco",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    numero_cheque = forms.CharField(
        required=False,
        label="Número de cheque",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # ======================================================
    # CONSTRUCTOR (FILTRA CUOTAS PENDIENTES)
    # ======================================================
    def __init__(self, *args, **kwargs):
        self.cuenta = kwargs.pop('cuenta', None)
        super().__init__(*args, **kwargs)

        if self.cuenta:
            self.fields['cuota'].queryset = CuotaPlan.objects.filter(
                plan__cuenta=self.cuenta,
                estado='pendiente'
            ).order_by('numero')

    # ======================================================
    # VALIDACIONES DE NEGOCIO (BLINDAJE)
    # ======================================================
    def clean(self):
        cleaned_data = super().clean()

        forma_pago = cleaned_data.get('forma_pago')
        banco = cleaned_data.get('banco')
        numero_cheque = cleaned_data.get('numero_cheque')
        monto = cleaned_data.get('monto') or Decimal('0')
        cuota = cleaned_data.get('cuota')

        if monto <= 0:
            self.add_error(
                'monto',
                'El monto debe ser mayor a cero.'
            )
            return cleaned_data

        if forma_pago == 'cheque':
            if not banco:
                self.add_error(
                    'banco',
                    'Debe indicar el banco del cheque.'
                )
            if not numero_cheque:
                self.add_error(
                    'numero_cheque',
                    'Debe indicar el número de cheque.'
                )

        if self.cuenta and self.cuenta.saldo is not None:
            if monto > self.cuenta.saldo:
                self.add_error(
                    'monto',
                    'El monto ingresado supera el saldo total de la cuenta.'
                )

        if cuota:
            total_pendiente_plan = sum(
                c.monto for c in CuotaPlan.objects.filter(
                    plan=cuota.plan,
                    estado='pendiente'
                )
            )

            if monto > total_pendiente_plan:
                self.add_error(
                    'monto',
                    'El monto ingresado supera lo pendiente del plan de pago.'
                )

        return cleaned_data

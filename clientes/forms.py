from django import forms
from django.db.models import Q
from .models import Cliente


class ClienteForm(forms.ModelForm):

    def clean(self):
        """Evita cargar el mismo cliente dos veces.

        Criterio: si tiene DNI/CUIT, no puede repetirse. Si no tiene DNI/CUIT,
        no puede repetirse el nombre completo. Se compara contra los clientes
        activos y se excluye el propio registro al editar.
        """
        cleaned = super().clean()
        nombre = (cleaned.get('nombre_completo') or '').strip()
        dni = (cleaned.get('dni_cuit') or '').strip()

        qs = Cliente.objects.filter(activo=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if dni:
            if qs.filter(dni_cuit__iexact=dni).exists():
                self.add_error(
                    'dni_cuit',
                    'Ya existe un cliente con este DNI/CUIT en el listado.'
                )
        elif nombre:
            duplicado = (
                qs.filter(nombre_completo__iexact=nombre)
                  .filter(Q(dni_cuit__isnull=True) | Q(dni_cuit__exact=''))
                  .exists()
            )
            if duplicado:
                self.add_error(
                    'nombre_completo',
                    'Ya existe un cliente con este nombre. Si es otra persona, '
                    'cargá el DNI/CUIT para diferenciarlos.'
                )
        return cleaned

    class Meta:
        model = Cliente
        fields = [
            'nombre_completo',
            'telefono',
            'email',
            'dni_cuit',
            'direccion',
        ]

        widgets = {
            'nombre_completo': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Nombre y apellido'
                }
            ),
            'telefono': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Teléfono de contacto'
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Email'
                }
            ),
            'dni_cuit': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'DNI o CUIT'
                }
            ),
            'direccion': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Dirección'
                }
            ),
        }

from django import forms
from .models import Proyecto, Tarea, Recordatorio


class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'color', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proyecto',
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
                'style': 'width: 70px; height: 42px; padding: 4px;',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción (opcional)',
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class TareaForm(forms.ModelForm):
    class Meta:
        model = Tarea
        fields = ['proyecto', 'titulo', 'descripcion', 'estado',
                  'prioridad', 'deadline']
        widgets = {
            'proyecto': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título de la tarea',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas (opcional)',
            }),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Limita las opciones del select de proyecto a los del usuario
        if user is not None:
            self.fields['proyecto'].queryset = Proyecto.objects.filter(
                usuario=user, activo=True
            )
        # datetime-local necesita el valor en este formato al editar
        self.fields['deadline'].input_formats = ['%Y-%m-%dT%H:%M']


class RecordatorioForm(forms.ModelForm):
    class Meta:
        model = Recordatorio
        fields = ['titulo', 'fecha_hora', 'tarea']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título del recordatorio',
            }),
            'fecha_hora': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }, format='%Y-%m-%dT%H:%M'),
            'tarea': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['tarea'].queryset = Tarea.objects.filter(usuario=user)
        self.fields['tarea'].required = False
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M']

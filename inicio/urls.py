from django.contrib import admin
from django.urls import path, include
from inicio import views as inicio_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # LOGIN
    path('', inicio_views.ingreso, name='ingreso'),

    # DASHBOARD
    path('inicio/', inicio_views.inicio, name='inicio'),

    # RECORDATORIOS
    path('recordatorios/agregar/', inicio_views.agregar_recordatorio, name='agregar_recordatorio'),
    path('recordatorios/<int:pk>/completar/', inicio_views.completar_recordatorio, name='completar_recordatorio'),
    path('recordatorios/<int:pk>/eliminar/', inicio_views.eliminar_recordatorio, name='eliminar_recordatorio'),

    # APPS
    path('vehiculos/', include('vehiculos.urls')),
    path('clientes/', include('clientes.urls')),
]

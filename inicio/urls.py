from django.contrib import admin
from django.urls import path, include
from inicio import views as inicio_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # LOGIN
    path('', inicio_views.ingreso, name='ingreso'),

    # DASHBOARD
    path('inicio/', inicio_views.inicio, name='inicio'),

    # APPS
    path('vehiculos/', include('vehiculos.urls')),
    path('clientes/', include('clientes.urls')),
]

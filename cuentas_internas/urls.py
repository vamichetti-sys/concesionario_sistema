from django.urls import path
from . import views

app_name = 'cuentas_internas'

urlpatterns = [
    path('', views.lista_cuentas, name='lista'),
    path('nueva/', views.crear_cuenta, name='crear'),
    path('<int:pk>/', views.detalle_cuenta, name='detalle'),
    path('<int:pk>/editar/', views.editar_cuenta, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar_cuenta, name='eliminar'),
    path('<int:pk>/movimiento/', views.agregar_movimiento, name='agregar_movimiento'),
    path('movimiento/<int:pk>/eliminar/', views.eliminar_movimiento, name='eliminar_movimiento'),
]
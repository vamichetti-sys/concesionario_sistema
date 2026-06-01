from django.urls import path
from . import views

app_name = 'cuentas_internas'

urlpatterns = [
    # Hub con las dos secciones
    path('', views.hub, name='hub'),

    # ===== ALQUILERES =====
    path('alquileres/', views.alquileres_lista, name='alquileres_lista'),
    path('alquileres/pdf/', views.alquileres_pdf, name='alquileres_pdf'),
    path('alquileres/nuevo/', views.alquiler_crear, name='alquiler_crear'),
    path('alquileres/pago/<int:pk>/eliminar/', views.alquiler_pago_eliminar, name='alquiler_pago_eliminar'),
    path('alquileres/<int:pk>/', views.alquiler_detalle, name='alquiler_detalle'),
    path('alquileres/<int:pk>/editar/', views.alquiler_editar, name='alquiler_editar'),
    path('alquileres/<int:pk>/eliminar/', views.alquiler_eliminar, name='alquiler_eliminar'),

    # ===== CUENTAS INTERNAS =====
    path('cuentas/', views.lista_cuentas, name='lista'),
    path('nueva/', views.crear_cuenta, name='crear'),
    path('<int:pk>/', views.detalle_cuenta, name='detalle'),
    path('<int:pk>/editar/', views.editar_cuenta, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar_cuenta, name='eliminar'),
    path('<int:pk>/movimiento/', views.agregar_movimiento, name='agregar_movimiento'),
    path('movimiento/<int:pk>/eliminar/', views.eliminar_movimiento, name='eliminar_movimiento'),
    path('pdf/mensual/', views.pdf_mensual, name='pdf_mensual'),
]
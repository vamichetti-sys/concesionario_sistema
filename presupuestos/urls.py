from django.urls import path
from . import views

app_name = 'presupuestos'

urlpatterns = [
    path('', views.lista_presupuestos, name='lista'),
    path('nuevo/', views.crear_presupuesto, name='crear'),
    path('<int:pk>/', views.detalle_presupuesto, name='detalle'),
    path('<int:pk>/editar/', views.editar_presupuesto, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar_presupuesto, name='eliminar'),
    path('<int:pk>/marcar-enviado/', views.marcar_enviado, name='marcar_enviado'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado, name='cambiar_estado'),
    path('cotizador/', views.cotizador, name='cotizador'),
    path('cotizador/pdf/', views.cotizador_pdf, name='cotizador_pdf'),
]
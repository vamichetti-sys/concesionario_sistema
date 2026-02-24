from django.urls import path
from . import views

app_name = 'cheques'

urlpatterns = [
    path('', views.lista_cheques, name='lista'),
    path('nuevo/', views.crear_cheque, name='crear'),
    path('<int:pk>/editar/', views.editar_cheque, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar_cheque, name='eliminar'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado_cheque, name='cambiar_estado'),
]
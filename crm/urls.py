from django.urls import path
from . import views

app_name = "crm"

urlpatterns = [
    path("", views.lista_prospectos, name="lista"),
    path("nuevo/", views.crear_prospecto, name="crear"),
    path("<int:pk>/", views.detalle_prospecto, name="detalle"),
    path("<int:pk>/editar/", views.editar_prospecto, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_prospecto, name="eliminar"),
    path("<int:pk>/etapa/", views.cambiar_etapa, name="cambiar_etapa"),
    path("<int:pk>/seguimiento/", views.agregar_seguimiento, name="agregar_seguimiento"),
    path("<int:pk>/convertir/", views.convertir_a_cliente, name="convertir"),
    path("notificacion/<int:pk>/leida/", views.marcar_notificacion_leida, name="marcar_leida"),
]

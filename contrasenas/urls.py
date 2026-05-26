from django.urls import path
from . import views

app_name = "contrasenas"

urlpatterns = [
    path("", views.lista_contrasenas, name="lista"),
    path("nueva/", views.crear_contrasena, name="crear"),
    path("<int:pk>/editar/", views.editar_contrasena, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_contrasena, name="eliminar"),
]

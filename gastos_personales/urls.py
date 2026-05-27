from django.urls import path
from . import views

app_name = "gastos_personales"

urlpatterns = [
    path("", views.lista_gastos, name="lista"),
    path("nuevo/", views.crear_gasto, name="crear"),
    path("<int:pk>/editar/", views.editar_gasto, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_gasto, name="eliminar"),
]

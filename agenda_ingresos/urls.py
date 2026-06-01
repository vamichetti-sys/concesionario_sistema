from django.urls import path
from . import views

app_name = "agenda_ingresos"

urlpatterns = [
    path("", views.lista_ingresos, name="lista"),
    path("nuevo/", views.crear_ingreso, name="crear"),
    path("<int:pk>/editar/", views.editar_ingreso, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_ingreso, name="eliminar"),
    path("<int:pk>/cobrar/", views.marcar_cobrado, name="marcar_cobrado"),
    path("<int:pk>/deshacer/", views.deshacer_cobro, name="deshacer_cobro"),
]

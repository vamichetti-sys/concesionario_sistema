from django.urls import path
from . import views


app_name = "financiacion"

urlpatterns = [
    path("", views.index, name="index"),
    path("financieras/nueva/", views.crear_financiera, name="crear_financiera"),
    path("financieras/<int:pk>/editar/", views.editar_financiera, name="editar_financiera"),
    path("financieras/<int:pk>/eliminar/", views.eliminar_financiera, name="eliminar_financiera"),
    path("ventas/<int:venta_id>/asignar-financiera/", views.asignar_financiera, name="asignar_financiera"),
]

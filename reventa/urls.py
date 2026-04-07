from django.urls import path
from . import views

app_name = "reventa"

urlpatterns = [
    # Reventas
    path("", views.lista_reventas, name="lista"),
    path("asignar/<int:vehiculo_id>/", views.asignar_reventa, name="asignar"),
    path("editar/<int:reventa_id>/", views.editar_reventa, name="editar"),
    path("revertir/<int:reventa_id>/", views.revertir_reventa, name="revertir"),
    path("eliminar/<int:reventa_id>/", views.eliminar_reventa, name="eliminar"),

    # Cuentas de revendedores
    path("cuentas/", views.lista_cuentas_revendedores, name="cuentas"),
    path("cuentas/nueva/", views.crear_cuenta_revendedor, name="crear_cuenta"),
    path("cuentas/<int:pk>/", views.detalle_cuenta_revendedor, name="detalle_cuenta"),
    path("cuentas/<int:pk>/movimiento/", views.agregar_movimiento_revendedor, name="agregar_movimiento"),
    path("movimiento/<int:pk>/eliminar/", views.eliminar_movimiento_revendedor, name="eliminar_movimiento"),
]

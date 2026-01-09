from django.urls import path
from . import views

# ✅ NAMESPACE CORRECTO
app_name = "ventas"

urlpatterns = [

    # ===============================
    # LISTADO DE UNIDADES VENDIDAS
    # ===============================
    path(
        "",
        views.lista_unidades_vendidas,
        name="lista_unidades_vendidas"
    ),

    # ===============================
    # ASIGNAR CLIENTE A VENTA
    # ===============================
    path(
        "asignar-cliente/<int:vehiculo_id>/",
        views.asignar_cliente_venta,
        name="asignar_cliente_venta"
    ),

    # ===============================
    # BUSCAR CLIENTE (AJAX)
    # ===============================
    path(
        "buscar-cliente/",
        views.buscar_cliente_venta,
        name="buscar_cliente_venta"
    ),

    # ===============================
    # MÁS INFO / DETALLE DE VENTA
    # ===============================
    path(
        "crear/<int:venta_id>/",
        views.crear_venta,
        name="crear_venta"
    ),

    # ===============================
    # REVERTIR VENTA
    # ===============================
    path(
        "revertir/<int:venta_id>/",
        views.revertir_venta,
        name="revertir_venta"
    ),
]

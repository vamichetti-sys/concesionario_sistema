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
    # PDF DEL LISTADO
    # ===============================
    path(
        "pdf/",
        views.pdf_unidades_vendidas,
        name="pdf_unidades_vendidas"
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

    # ===============================
    # ACTUALIZAR PRECIO DE VENTA
    # ===============================
    path(
        "precio/<int:venta_id>/",
        views.actualizar_precio_venta,
        name="actualizar_precio_venta"
    ),

    # ===============================
    # COMISIONES POR VENDEDOR (solo admin)
    # ===============================
    path(
        "comisiones/",
        views.comisiones_vendedores,
        name="comisiones_vendedores"
    ),
    path(
        "comisiones/<int:user_id>/",
        views.detalle_comision_vendedor,
        name="detalle_comision_vendedor"
    ),
    path(
        "comisiones/registrar/",
        views.registrar_comision,
        name="registrar_comision"
    ),
    path(
        "comisiones/pago/",
        views.registrar_pago_comision,
        name="registrar_pago_comision"
    ),
    path(
        "comisiones/movimiento/<int:movimiento_id>/eliminar/",
        views.eliminar_movimiento_comision,
        name="eliminar_movimiento_comision"
    ),
]

from django.urls import path
from . import views

app_name = "compraventa"

urlpatterns = [
    # =========================
    # HOME
    # =========================
    path("", views.compraventa_home, name="home"),

    # =========================
    # PROVEEDORES
    # =========================
    path("proveedor/nuevo/", views.proveedor_crear, name="proveedor_crear"),
    path(
        "proveedor/<int:proveedor_id>/",
        views.proveedor_detalle,
        name="proveedor_detalle"
    ),

    path(
    "proveedor/<int:proveedor_id>/eliminar/",
    views.proveedor_eliminar,
    name="proveedor_eliminar"
    ),


    # =========================
    # COMPRAS
    # =========================
    path("compra/nueva/", views.compra_registrar, name="compra_registrar"),
    path(
        "proveedor/<int:proveedor_id>/compra/nueva/",
        views.compra_registrar,
        name="compra_registrar_proveedor"
    ),

    # =========================
    # PAGOS
    # =========================
    path(
        "deuda/<int:deuda_id>/pago/nuevo/",
        views.deuda_registrar_pago,
        name="deuda_pago"
    ),
    
    # =========================
    # EDITAR DEUDA
    # =========================
    path(
        "deuda/<int:deuda_id>/editar/",
        views.deuda_editar,
        name="deuda_editar"
    ),

    # =========================
    # UNIDADES
    # =========================
    path(
        "proveedor/<int:proveedor_id>/unidades/",
        views.proveedor_unidades,
        name="proveedor_unidades"
    ),

    # =========================
    # CUENTA CORRIENTE
    # =========================
    path(
        "proveedor/<int:proveedor_id>/cuenta-corriente/",
        views.proveedor_cuenta_corriente,
        name="proveedor_cuenta_corriente"
    ),
]

from django.urls import path
from . import views

# Namespace del módulo clientes
app_name = "clientes"

urlpatterns = [

    # ===============================
    # API CLIENTE (BOLETOS - AJAX)
    # ===============================
    path(
        "ajax/cliente-datos/",
        views.cliente_datos_ajax,
        name="cliente_datos_ajax"
    ),

    # ===============================
    # API CLIENTE (AUTOCOMPLETADO)
    # ===============================
    path(
        "api/cliente/<int:cliente_id>/",
        views.cliente_json,
        name="cliente_json"
    ),

    # ===============================
    # LISTA DE CLIENTES
    # ===============================
    path(
        "",
        views.lista_clientes,
        name="lista_clientes"
    ),

    # ===============================
    # CREAR CLIENTE
    # ===============================
    path(
        "agregar/",
        views.crear_cliente,
        name="crear_cliente"
    ),

    # ===============================
    # EDITAR CLIENTE
    # ===============================
    path(
        "<int:cliente_id>/editar/",
        views.editar_cliente,
        name="editar_cliente"
    ),

    # ===============================
    # DESACTIVAR CLIENTE (ELIMINACIÓN LÓGICA)
    # ===============================
    path(
        "desactivar/<int:cliente_id>/",
        views.desactivar_cliente,
        name="desactivar_cliente"
    ),

    # ===============================
    # DETALLE DE CLIENTE
    # ⚠️ SIEMPRE AL FINAL
    # ===============================
    path(
        "<int:cliente_id>/",
        views.detalle_cliente,
        name="detalle_cliente"
    ),
]

from django.urls import path
from . import views

# 🔑 namespace de la app
app_name = "vehiculos"

urlpatterns = [
    # ==================================================
    # AJAX – DATOS DE VEHÍCULO (PARA BOLETOS)
    # ==================================================
    path(
        "ajax/vehiculo-datos/",
        views.vehiculo_datos_ajax,
        name="vehiculo_datos_ajax"
    ),
    # Alias de compatibilidad
    path(
        "vehiculo-datos-ajax/",
        views.vehiculo_datos_ajax,
        name="vehiculo_datos_ajax_alias"
    ),
    # ==================================================
    # LISTADOS
    # ==================================================
    path(
        "",
        views.lista_vehiculos,
        name="lista_vehiculos"
    ),
    path(
        "vendidos/",
        views.lista_vehiculos_vendidos,
        name="lista_vehiculos_vendidos"
    ),
    # ==================================================
    # ALTA / BAJA DE VEHÍCULOS
    # ==================================================
    path(
        "agregar/",
        views.agregar_vehiculo,
        name="agregar_vehiculo"
    ),
    path(
        "eliminar/<int:vehiculo_id>/",
        views.eliminar_vehiculo,
        name="eliminar_vehiculo"
    ),
    # ==================================================
    # ESTADO DEL VEHÍCULO
    # ==================================================
    path(
        "cambiar-estado/<int:vehiculo_id>/",
        views.cambiar_estado_vehiculo,
        name="cambiar_estado_vehiculo"
    ),
    # ==================================================
    # FICHA VEHICULAR
    # ==================================================
    path(
        "ficha-vehicular/<int:vehiculo_id>/",
        views.ficha_vehicular_ajax,
        name="ficha_vehicular_ajax"
    ),
    path(
        "guardar-ficha/<int:vehiculo_id>/",
        views.guardar_ficha_vehicular,
        name="guardar_ficha_vehicular"
    ),
    path(
        "ficha-completa/<int:vehiculo_id>/",
        views.ficha_completa,
        name="ficha_completa"
    ),
    # ==================================================
    # GUARDAR FICHA PARCIAL (TITULARIDAD + DOCUMENTACIÓN)
    # ==================================================
    path(
        "ficha-parcial/<int:vehiculo_id>/",
        views.guardar_ficha_parcial,
        name="guardar_ficha_parcial"
    ),
    # ==================================================
    # 👉 ALIAS AGREGADO (NO SE ELIMINA NADA)
    # 👉 SOLO PARA COMPATIBILIDAD CON UNIDADES
    # ==================================================
    path(
        "ficha/<int:vehiculo_id>/",
        views.ficha_completa,
        name="ficha_vehicular"
    ),
    # ==================================================
    # PDF – LISTADO DE STOCK
    # ==================================================
    path(
        "stock/pdf/",
        views.stock_pdf,
        name="stock_pdf"
    ),
    # ==================================================
    # PDF – FICHA VEHICULAR
    # ==================================================
    path(
        "pdf/<int:vehiculo_id>/",
        views.ficha_vehicular_pdf,
        name="ficha_vehicular_pdf"
    ),
    # ==================================================
    # GASTOS – OPERATIVOS EXISTENTES
    # ==================================================
    path(
        "gastos-ingreso/<int:vehiculo_id>/",
        views.agregar_gasto_ingreso,
        name="agregar_gasto_ingreso"
    ),
    # 🔴 CORREGIDO: SIN vehiculo_id EN LA URL
    path(
        "pago-gasto/",
        views.registrar_pago_gasto,
        name="registrar_pago_gasto"
    ),
    path(
        "pago-gasto/eliminar/<int:pago_id>/",
        views.eliminar_pago_gasto,
        name="eliminar_pago_gasto"
    ),
    # ==================================================
    # GASTOS CONCESIONARIO
    # ==================================================
    path(
        "gastos-concesionario/<int:vehiculo_id>/",
        views.guardar_gastos_concesionario,
        name="guardar_gastos_concesionario"
    ),
    path(
        "gasto-extra/<int:vehiculo_id>/",
        views.agregar_gasto_extra,
        name="agregar_gasto_extra"
    ),
    path(
        "gasto-extra/eliminar/<int:pk>/",
        views.eliminar_gasto_extra,
        name="eliminar_gasto_extra"
    ),
    # ==================================================
    # GASTOS – CONFIGURACIÓN GLOBAL
    # ==================================================
    path(
        "gastos/",
        views.gastos_configuracion,
        name="gastos"
    ),
    # ==================================================
    # TEST (OPCIONAL – PODÉS BORRARLO CUANDO QUIERAS)
    # ==================================================
    path(
        "test-gastos/",
        views.test_guardado_gastos,
        name="test_guardado_gastos"
    ),
    # ==================================================
    # MANTENIMIENTOS
    # ==================================================
    path(
        "mantenimiento/<int:vehiculo_id>/agregar/",
        views.agregar_mantenimiento,
        name="agregar_mantenimiento"
    ),
    path(
        "mantenimiento/eliminar/<int:pk>/",
        views.eliminar_mantenimiento,
        name="eliminar_mantenimiento"
    ),
]
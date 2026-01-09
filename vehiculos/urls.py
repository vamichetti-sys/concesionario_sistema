from django.urls import path
from . import views

# 🔑 IMPORTANTE: namespace de la app
app_name = "vehiculos"

urlpatterns = [

    # ==================================================
    # AJAX – DATOS DE VEHÍCULO (PARA BOLETOS)
    # ⚠️ DEBE IR ANTES DE RUTAS CON <int:vehiculo_id>
    # ==================================================
    path(
        "ajax/vehiculo-datos/",
        views.vehiculo_datos_ajax,
        name="vehiculo_datos_ajax"
    ),

    # ==================================================
    # ✅ ALIAS PARA AUTOCOMPLETADO (NUEVA RUTA)
    # 👉 USADA POR crear.html
    # 👉 NO rompe compatibilidad
    # ==================================================
    path(
        "vehiculo-datos-ajax/",
        views.vehiculo_datos_ajax,
        name="vehiculo_datos_ajax_alias"
    ),

    # ==================================================
    # LISTA DE VEHÍCULOS (STOCK + TEMPORALES)
    # ==================================================
    path(
        "",
        views.lista_vehiculos,
        name="lista_vehiculos"
    ),

    # ==================================================
    # LISTA DE VEHÍCULOS VENDIDOS
    # ==================================================
    path(
        "vendidos/",
        views.lista_vehiculos_vendidos,
        name="lista_vehiculos_vendidos"
    ),

    # ==================================================
    # AGREGAR VEHÍCULO
    # ==================================================
    path(
        "agregar/",
        views.agregar_vehiculo,
        name="agregar_vehiculo"
    ),

    # ==================================================
    # 🔴 CAMBIAR ESTADO DE VEHÍCULO (PUNTO CLAVE DEL FLUJO)
    # 👉 Dispara: Venta + Cuenta Corriente + Gestoría
    # ==================================================
    path(
        "cambiar-estado/<int:vehiculo_id>/",
        views.cambiar_estado_vehiculo,
        name="cambiar_estado_vehiculo"
    ),

    # ==================================================
    # MODAL FICHA VEHICULAR (AJAX - GET)
    # ==================================================
    path(
        "ficha-vehicular/<int:vehiculo_id>/",
        views.ficha_vehicular_ajax,
        name="ficha_vehicular_ajax"
    ),

    # ==================================================
    # GUARDAR FICHA VEHICULAR (POST)
    # 👉 RUTA USADA POR EL BOTÓN "GUARDAR CAMBIOS"
    # ==================================================
    path(
        "guardar-ficha/<int:vehiculo_id>/",
        views.guardar_ficha_vehicular,
        name="guardar_ficha_vehicular"
    ),

    # ==================================================
    # FICHA COMPLETA DEL VEHÍCULO (PÁGINA)
    # ==================================================
    path(
        "ficha-completa/<int:vehiculo_id>/",
        views.ficha_completa,
        name="ficha_completa"
    ),

    # ==================================================
    # 💰 REGISTRAR PAGO DE GASTO (NUEVO – PAGO DE GASTOS)
    # 👉 USADO POR LA SOLAPA "PAGO DE GASTOS"
    # ==================================================
    path(
        "pago-gasto/<int:vehiculo_id>/",
        views.registrar_pago_gasto,
        name="registrar_pago_gasto"
    ),

  # ==================================================
# PDF FICHA VEHICULAR
# ==================================================
# path(
#     "pdf/<int:vehiculo_id>/",
#     views.ficha_vehicular_pdf,
#     name="ficha_vehicular_pdf",
# ),


    # ==================================================
    # ❌ ELIMINAR VEHÍCULO
    # ==================================================
    path(
        "eliminar/<int:vehiculo_id>/",
        views.eliminar_vehiculo,
        name="eliminar_vehiculo"
    ),

    # ==================================================
    # 🟠 GASTOS DE INGRESO (DESDE CUENTA CORRIENTE)
    # 👉 USADO POR EL BOTÓN "Cargar gasto de ingreso"
    # ==================================================
    path(
        "gastos-ingreso/<int:vehiculo_id>/",
        views.agregar_gasto_ingreso,
        name="agregar_gasto_ingreso"
    ),
]

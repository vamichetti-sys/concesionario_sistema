from django.urls import path
from . import views

app_name = "cuentas"

urlpatterns = [

    # ===============================
    # LISTA DE CUENTAS CORRIENTES
    # ===============================
    path(
        "",
        views.lista_cuentas_corrientes,
        name="lista_cuentas_corrientes"
    ),

    # ===============================
    # CREAR CUENTA CORRIENTE
    # ===============================
    path(
        "crear/<int:cliente_id>/",
        views.crear_cuenta_corriente,
        name="crear_cuenta_corriente"
    ),

    # ===============================
    # REGISTRAR MOVIMIENTO / PAGO
    # ===============================
    path(
        "<int:cuenta_id>/movimiento/",
        views.registrar_movimiento,
        name="registrar_movimiento"
    ),

    # ===============================
    # PAGAR / EDITAR CUOTA
    # ===============================
    path(
        "cuota/<int:cuota_id>/pagar/",
        views.pagar_cuota,
        name="pagar_cuota"
    ),
    path(
        "cuota/<int:cuota_id>/editar/",
        views.editar_cuota,
        name="editar_cuota"
    ),

    # ===============================
    # PLAN DE PAGO
    # ===============================
    path(
        "<int:cuenta_id>/plan/",
        views.crear_plan_pago,
        name="crear_plan_pago"
    ),
    path(
        "<int:cuenta_id>/plan/eliminar/",
        views.eliminar_plan_pago,
        name="eliminar_plan_pago"
    ),

    # ===============================
    # AGREGAR / VINCULAR GASTOS
    # ===============================
    path(
        "<int:cuenta_id>/agregar-gasto/",
        views.agregar_gasto_cuenta,
        name="agregar_gasto_cuenta"
    ),
    path(
        "<int:cuenta_id>/permuta/<int:vehiculo_id>/",
        views.conectar_vehiculo_permuta,
        name="conectar_vehiculo_permuta"
    ),

    # ===============================
    # RECIBO DE PAGO
    # ===============================
    path(
        "pago/<int:pago_id>/recibo/",
        views.recibo_pago_pdf,
        name="recibo_pago_pdf"
    ),

    # ==================================================
    # HISTORIAL DE FINANCIACIÓN (CUENTA CERRADA)
    # ==================================================
    path(
        "historial/<int:cuenta_id>/",
        views.historial_financiacion,
        name="historial_financiacion"
    ),

    # ===============================
    # DETALLE DE CUENTA CORRIENTE
    # ⚠️ SIEMPRE AL FINAL
    # ===============================
    path(
        "<int:cuenta_id>/",
        views.cuenta_corriente_detalle,
        name="cuenta_corriente_detalle"
    ),

    # ===============================
    # ELIMINAR CUENTA CORRIENTE
    # ===============================
    path(
        "<int:cuenta_id>/eliminar/",
        views.eliminar_cuenta_corriente,
        name="eliminar_cuenta_corriente"
    ),
]

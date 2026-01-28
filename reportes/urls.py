from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    # ==========================
    # PANTALLA PRINCIPAL
    # ==========================
    path("", views.lista_reportes, name="lista"),

    # ==========================
    # REPORTE WEB (sistema)
    # ==========================
    path("web/", views.reporte_web, name="reporte_web"),

    # ==========================
    # REPORTE INTERNO
    # ==========================
    path("interno/", views.reporte_interno, name="reporte_interno"),
    path("interno/stock/", views.control_stock, name="control_stock"),
    path("interno/reporte/", views.reporte_ganancias, name="reporte_ganancias"),
    path(
    "interno/vamichetti/",
    views.reporte_interno_vamichetti,
    name="reporte_interno_vamichetti"
),


    # ==========================
    # EDITAR FICHA INTERNA
    # ==========================
    path(
        "interno/ficha/<int:vehiculo_id>/editar/",
        views.editar_ficha_reporte,
        name="editar_ficha_reporte"
    ),

    # ==========================
    # GASTOS REPORTE INTERNO  ✅ (ESTO FALTABA)
    # ==========================
    path(
        "interno/ficha/<int:ficha_id>/gasto/agregar/",
        views.agregar_gasto_reporte,
        name="agregar_gasto_reporte"
    ),
    path(
        "interno/gasto/<int:gasto_id>/eliminar/",
        views.eliminar_gasto_reporte,
        name="eliminar_gasto_reporte"
    ),

    # ==========================
    # CIERRES
    # ==========================
    path("cerrar/mes/", views.cerrar_mes, name="cerrar_mes"),
    path("cerrar/anio/", views.cerrar_anio, name="cerrar_anio"),
]

from django.urls import path
from . import views

app_name = "facturacion"

urlpatterns = [
    # Facturas (ventas)
    path("", views.lista_facturacion, name="lista"),
    path("crear/", views.crear_factura, name="crear"),
    path("<int:pk>/eliminar/", views.eliminar_factura, name="eliminar"),

    # Compras
    path("compras/", views.lista_compras, name="compras"),
    path("compras/crear/", views.crear_compra, name="crear_compra"),
    path("compras/<int:pk>/eliminar/", views.eliminar_compra, name="eliminar_compra"),

    # IVA
    path("iva/", views.posicion_iva, name="iva"),

    # Exportaciones
    path("exportar/excel/mensual/", views.exportar_excel_mensual, name="excel_mensual"),
    path("exportar/excel/anual/", views.exportar_excel_anual, name="excel_anual"),
    path("exportar/pdf/mensual/", views.exportar_pdf_mensual, name="pdf_mensual"),
    path("exportar/pdf/anual/", views.exportar_pdf_anual, name="pdf_anual"),
]

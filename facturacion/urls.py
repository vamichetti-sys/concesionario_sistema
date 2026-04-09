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
    path("iva/pdf/", views.iva_pdf, name="iva_pdf"),

    # Exportaciones facturas
    path("exportar/excel/mensual/", views.exportar_excel_mensual, name="excel_mensual"),
    path("exportar/excel/anual/", views.exportar_excel_anual, name="excel_anual"),
    path("exportar/pdf/mensual/", views.exportar_pdf_mensual, name="pdf_mensual"),
    path("exportar/pdf/anual/", views.exportar_pdf_anual, name="pdf_anual"),

    # Exportaciones compras
    path("compras/exportar/pdf/mensual/", views.compras_pdf_mensual, name="compras_pdf_mensual"),
    path("compras/exportar/pdf/anual/", views.compras_pdf_anual, name="compras_pdf_anual"),
    path("compras/exportar/excel/mensual/", views.compras_excel_mensual, name="compras_excel_mensual"),
    path("compras/exportar/excel/anual/", views.compras_excel_anual, name="compras_excel_anual"),
]

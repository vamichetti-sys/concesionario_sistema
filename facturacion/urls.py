from django.urls import path
from . import views

app_name = "facturacion"

urlpatterns = [
    path("", views.lista_facturacion, name="lista"),
    path("crear/", views.crear_factura, name="crear"),

    # EXPORTACIONES
    path("exportar/excel/mensual/", views.exportar_excel_mensual, name="excel_mensual"),
    path("exportar/excel/anual/", views.exportar_excel_anual, name="excel_anual"),
    path("exportar/pdf/mensual/", views.exportar_pdf_mensual, name="pdf_mensual"),
    path("exportar/pdf/anual/", views.exportar_pdf_anual, name="pdf_anual"),
]

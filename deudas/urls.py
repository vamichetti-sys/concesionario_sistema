from django.urls import path
from . import views

app_name = "deudas"

urlpatterns = [
    path(
        "",
        views.listado_deudas,
        name="listado"
    ),
    path(
        "pdf/",
        views.pdf_listado_deudas,
        name="pdf_listado"
    ),
    path(
        "situacion/",
        views.deudas_situacion,
        name="situacion"
    ),
]

from django.urls import path
from . import views

app_name = "deudas"

urlpatterns = [
    path(
        "",
        views.listado_deudas,
        name="listado"
    ),
]

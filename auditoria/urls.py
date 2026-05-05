from django.urls import path
from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.lista_logs, name="lista_logs"),
    path("eliminados/", views.lista_eliminados, name="lista_eliminados"),
    path("restaurar/<int:log_id>/", views.restaurar_registro, name="restaurar_registro"),
]

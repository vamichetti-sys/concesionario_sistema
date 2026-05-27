from django.urls import path
from . import views

app_name = "permisos"

urlpatterns = [
    path("", views.gestionar_permisos, name="gestionar"),
]

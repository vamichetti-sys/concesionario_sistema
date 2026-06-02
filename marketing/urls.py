from django.urls import path
from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("bandeja/", views.bandeja, name="bandeja"),
    path("conversacion/<int:pk>/", views.conversacion, name="conversacion"),
    path("leads/", views.leads, name="leads"),
    path("conexion/", views.conexion, name="conexion"),

    # Webhook público que llama Meta
    path("webhook/", views.webhook, name="webhook"),
]

from django.urls import path
from .views import inicio_reventa

app_name = "reventa"

urlpatterns = [
    path("", inicio_reventa, name="inicio"),
]

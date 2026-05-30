from django.urls import path
from . import views


app_name = "financiacion"

urlpatterns = [
    path("", views.index, name="index"),
]

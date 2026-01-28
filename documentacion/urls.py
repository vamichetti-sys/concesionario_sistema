from django.urls import path
from . import views

app_name = 'documentacion'

urlpatterns = [
    path('', views.documentacion_home, name='home'),
]
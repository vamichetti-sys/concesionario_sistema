from django.urls import path
from . import views

urlpatterns = [

    # ==================================================
    # 📅 CALENDARIO DE VENCIMIENTOS Y TURNOS
    # ==================================================
    path(
        '',
        views.calendario_vencimientos,
        name='calendario_vencimientos'
    ),

    # ==================================================
    # 📅 API EVENTOS DEL CALENDARIO (JSON)
    # ==================================================
    path(
        'api/eventos/',
        views.api_calendario_vencimientos,
        name='api_calendario_vencimientos'
    ),

    # ==================================================
    # 📄 PDF MENSUAL DEL CALENDARIO
    # ==================================================
    path(
        'pdf/<int:anio>/<int:mes>/',
        views.calendario_pdf_mensual,
        name='calendario_pdf_mensual'
    ),
]

from django.urls import path
from . import views

app_name = "boletos"

urlpatterns = [
    # PANEL
    path("", views.panel_boletos, name="panel"),

    # BOLETOS
    path("lista/", views.lista_boletos, name="lista"),
    path("nuevo/", views.crear_boleto_manual, name="crear_manual"),
    path("ver/<int:boleto_id>/", views.ver_boleto, name="ver_boleto"),
    path("imprimir/<int:boleto_id>/", views.imprimir_boleto, name="imprimir_boleto"),
    path("editar/<int:boleto_id>/", views.editar_boleto, name="editar_boleto"),
    path("eliminar/<int:boleto_id>/", views.eliminar_boleto, name="eliminar_boleto"),

    # PAGARÉS
    path("pagare/", views.lista_pagares, name="lista_pagares"),
    path("pagare/nuevo/", views.crear_pagares, name="crear_pagares"),
    path("pagare/ver/<int:pagare_id>/", views.ver_pagare, name="ver_pagare"),
    path("pagare/pdf/<int:pagare_id>/", views.pagare_pdf, name="pagare_pdf"),
    path("pagare/lote/<int:lote_id>/pdf/", views.descargar_pdf_lote, name="descargar_pdf_lote"),
    path("pagare/lote/<int:lote_id>/", views.ver_lote, name="ver_lote"),
    path("pagare/eliminar/<int:lote_id>/", views.eliminar_lote, name="eliminar_lote"),

    # RESERVAS
    path("reservas/", views.lista_reservas, name="lista_reservas"),
    path("reservas/nueva/", views.crear_reserva, name="crear_reserva"),
    path("reservas/ver/<int:reserva_id>/", views.ver_reserva, name="ver_reserva"),
    path("reservas/editar/<int:reserva_id>/", views.editar_reserva, name="editar_reserva"),
    path("reservas/eliminar/<int:reserva_id>/", views.eliminar_reserva, name="eliminar_reserva"),
    path("reservas/pdf/<int:reserva_id>/", views.reserva_pdf, name="reserva_pdf"),
]

from django.urls import path
from . import views

app_name = "boletos"

urlpatterns = [
    # ===============================
    # 🟢 PANEL DE ENTRADA
    # ===============================
    path(
        "",
        views.panel_boletos,
        name="panel"
    ),

    # ===============================
    # 📄 BOLETOS
    # ===============================
    path(
        "lista/",
        views.lista_boletos,
        name="lista"
    ),
    path(
        "nuevo/",
        views.crear_boleto_manual,
        name="crear_manual"
    ),
    path(
        "ver/<int:boleto_id>/",
        views.ver_boleto,
        name="ver_boleto"
    ),
    path(
        "editar/<int:boleto_id>/",
        views.editar_boleto,
        name="editar_boleto"
    ),

    # ===============================
    # 📝 PAGARÉS
    # ===============================
    path(
        "pagare/",
        views.lista_pagares,
        name="lista_pagares"
    ),
    path(
        "pagare/nuevo/",
        views.crear_pagares,
        name="crear_pagares"
    ),
    path(
        "pagare/ver/<int:pagare_id>/",
        views.ver_pagare,
        name="ver_pagare"
    ),
    path(
        "pagare/pdf/<int:pagare_id>/",
        views.pagare_pdf,
        name="pagare_pdf"
    ),
    path(
        'pagare/lote/<int:lote_id>/pdf/',
        views.descargar_pdf_lote,
        name='descargar_pdf_lote'
    ),
    path(
        'pagare/lote/<int:lote_id>/',
        views.ver_lote,
        name='ver_lote'
    ),
    path(
        'pagare/eliminar/<int:lote_id>/',
        views.eliminar_lote,
        name='eliminar_lote'
    ),
]
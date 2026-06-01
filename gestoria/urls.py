from django.urls import path
from . import views

app_name = "gestoria"

urlpatterns = [
    # ===============================
    # INICIO GESTORÍA
    # ===============================
    path("", views.gestoria_inicio, name="inicio"),

    # ===============================
    # LISTADOS
    # ===============================
    path("vigentes/", views.gestoria_vigentes, name="vigentes"),
    path("finalizadas/", views.gestoria_finalizadas, name="finalizadas"),
    path("pdf/", views.pdf_gestorias, name="pdf_gestorias"),
    path("pagos-concesionario/", views.pagos_concesionario, name="pagos_concesionario"),
    path("<int:gestoria_id>/pago-cliente/", views.generar_pago_cliente, name="generar_pago_cliente"),

    # ===============================
    # ACCIÓN: MARCAR COMO FINALIZADA
    # ===============================
    path(
        "finalizar/<int:gestoria_id>/",
        views.finalizar_gestoria,
        name="finalizar"
    ),

    # ===============================
    # 🆕 ACCIÓN: EDITAR FICHA DE GESTORÍA
    # ===============================
    path(
        "editar/<int:gestoria_id>/",
        views.editar_gestoria,
        name="editar_gestoria"
    ),
]

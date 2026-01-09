from django.urls import path
from . import views

app_name = "asistencia"

urlpatterns = [
    # ===============================
    # EMPLEADOS
    # ===============================
    path(
        "",
        views.lista_empleados,
        name="lista"
    ),

    path(
        "crear/",
        views.crear_empleado,
        name="crear_empleado"
    ),

    # ===============================
    # CALENDARIO POR EMPLEADO
    # ===============================
    path(
        "empleado/<int:empleado_id>/",
        views.calendario_empleado,
        name="calendario_empleado"
    ),

    # ===============================
    # MARCAR / MODIFICAR ASISTENCIA
    # ===============================
    path(
        "marcar/",
        views.marcar_asistencia,
        name="marcar_asistencia"
    ),

    # ===============================
    # PDF – FALTAS ANUALES
    # ===============================
    path(
        "pdf/faltas/<int:empleado_id>/<int:anio>/",
        views.pdf_faltas_anuales,
        name="pdf_faltas_anuales"
    ),
]

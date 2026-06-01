from django.urls import path
from . import views

app_name = "gastos_mensuales"

urlpatterns = [
    path("", views.resumen_mensual, name="resumen"),
    path("agregar/", views.agregar_gasto, name="agregar"),
    path("<int:pk>/editar/", views.editar_gasto, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_gasto, name="eliminar"),
    path("<int:pk>/pagado/", views.marcar_pagado, name="marcar_pagado"),
    path("<int:pk>/monto/", views.actualizar_monto, name="actualizar_monto"),
    path("pdf/mensual/", views.pdf_mensual, name="pdf_mensual"),
    path("duplicar-fijos/", views.duplicar_fijos, name="duplicar_fijos"),
    path("categorias/", views.lista_categorias, name="categorias"),
    path("categorias/nueva/", views.crear_categoria, name="crear_categoria"),
    path("categorias/<int:pk>/editar/", views.editar_categoria, name="editar_categoria"),

    # ===== CONTROL DE INGRESOS =====
    path("ingresos/", views.ingresos_resumen, name="ingresos"),
    path("ingresos/agregar/", views.agregar_ingreso, name="ingreso_agregar"),
    path("ingresos/<int:pk>/editar/", views.editar_ingreso, name="ingreso_editar"),
    path("ingresos/<int:pk>/eliminar/", views.eliminar_ingreso, name="ingreso_eliminar"),
    path("ingresos/<int:pk>/monto/", views.actualizar_monto_ingreso, name="ingreso_monto"),
    path("ingresos/pdf/", views.pdf_ingresos, name="ingresos_pdf"),
]

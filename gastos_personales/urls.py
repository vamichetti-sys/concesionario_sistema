from django.urls import path
from . import views

app_name = "gastos_personales"

urlpatterns = [
    path("", views.resumen_mensual, name="resumen"),
    path("agregar/", views.agregar_gasto, name="agregar"),
    path("<int:pk>/editar/", views.editar_gasto, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_gasto, name="eliminar"),
    path("<int:pk>/pagado/", views.marcar_pagado, name="marcar_pagado"),
    path("<int:pk>/monto/", views.actualizar_monto, name="actualizar_monto"),
    path("duplicar-fijos/", views.duplicar_fijos, name="duplicar_fijos"),
    # Compatibilidad: 'lista' apunta al resumen
    path("lista/", views.resumen_mensual, name="lista"),
    path("pdf/mensual/", views.pdf_mensual, name="pdf_mensual"),
]

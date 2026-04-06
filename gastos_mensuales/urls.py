from django.urls import path
from . import views

app_name = "gastos_mensuales"

urlpatterns = [
    path("", views.resumen_mensual, name="resumen"),
    path("agregar/", views.agregar_gasto, name="agregar"),
    path("<int:pk>/editar/", views.editar_gasto, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_gasto, name="eliminar"),
    path("<int:pk>/pagado/", views.marcar_pagado, name="marcar_pagado"),
    path("duplicar-fijos/", views.duplicar_fijos, name="duplicar_fijos"),
    path("categorias/", views.lista_categorias, name="categorias"),
    path("categorias/nueva/", views.crear_categoria, name="crear_categoria"),
    path("categorias/<int:pk>/editar/", views.editar_categoria, name="editar_categoria"),
]

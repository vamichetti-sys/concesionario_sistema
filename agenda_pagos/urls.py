from django.urls import path
from . import views

app_name = "agenda_pagos"

urlpatterns = [
    path("", views.lista_pagos, name="lista"),
    path("nuevo/", views.crear_pago, name="crear"),
    path("<int:pk>/editar/", views.editar_pago, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar_pago, name="eliminar"),
    path("<int:pk>/pagar/", views.marcar_pagado, name="marcar_pagado"),
    path("<int:pk>/deshacer/", views.deshacer_pago, name="deshacer_pago"),
    path("copiar-mes-anterior/", views.copiar_mes_anterior, name="copiar_mes_anterior"),
]

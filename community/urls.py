from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("", views.community_dashboard, name="dashboard"),
    path("vehiculo/<int:vehiculo_id>/fotos/", views.vehiculo_fotos, name="vehiculo_fotos"),
    path("foto/<int:foto_id>/eliminar/", views.eliminar_foto, name="eliminar_foto"),
    path("foto/<int:foto_id>/portada/", views.marcar_portada, name="marcar_portada"),
    path("vehiculo/<int:vehiculo_id>/toggle/<str:plataforma>/", views.toggle_publicacion, name="toggle_publicacion"),
    path("catalogo/", views.catalogo_publico, name="catalogo_publico"),
    path("catalogo/pdf/", views.catalogo_pdf, name="catalogo_pdf"),
    path("resumen/pdf/", views.resumen_publicaciones_pdf, name="resumen_publicaciones_pdf"),
]

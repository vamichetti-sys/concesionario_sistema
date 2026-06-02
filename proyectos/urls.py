from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    # Dashboard principal del módulo
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),

    # CRUD Proyectos
    path('proyectos/', views.proyecto_lista, name='proyecto_lista'),
    path('proyectos/nuevo/', views.proyecto_crear, name='proyecto_crear'),
    path('proyectos/<int:pk>/', views.proyecto_detail, name='proyecto_detail'),
    path('proyectos/<int:pk>/editar/', views.proyecto_editar, name='proyecto_editar'),
    path('proyectos/<int:pk>/eliminar/', views.proyecto_eliminar, name='proyecto_eliminar'),

    # CRUD Tareas
    path('tareas/', views.tarea_lista, name='tarea_lista'),
    path('tareas/nueva/', views.tarea_crear, name='tarea_crear'),
    path('tareas/<int:pk>/editar/', views.tarea_editar, name='tarea_editar'),
    path('tareas/<int:pk>/eliminar/', views.tarea_eliminar, name='tarea_eliminar'),
    path('tareas/<int:pk>/cambiar-estado/', views.tarea_cambiar_estado, name='tarea_cambiar_estado'),

    # Agenda diaria (to-do por día)
    path('agenda/', views.agenda_diaria, name='agenda_diaria'),
    path('agenda/agregar/', views.agenda_diaria_agregar, name='agenda_diaria_agregar'),
    path('agenda/<int:pk>/toggle/', views.agenda_diaria_toggle, name='agenda_diaria_toggle'),
    path('agenda/<int:pk>/editar/', views.agenda_diaria_editar, name='agenda_diaria_editar'),
    path('agenda/<int:pk>/eliminar/', views.agenda_diaria_eliminar, name='agenda_diaria_eliminar'),
    path('agenda/<int:pk>/mover-hoy/', views.agenda_diaria_mover_hoy, name='agenda_diaria_mover_hoy'),

    # Calendario
    path('calendario/', views.calendario, name='calendario'),
    path('calendario/eventos.json', views.calendario_eventos_json, name='calendario_eventos_json'),

    # Recordatorios
    path('recordatorios/', views.recordatorio_lista, name='recordatorio_lista'),
    path('recordatorios/<int:pk>/editar/', views.recordatorio_editar, name='recordatorio_editar'),
    path('recordatorios/<int:pk>/eliminar/', views.recordatorio_eliminar, name='recordatorio_eliminar'),

    # API
    path('api/recordatorios-pendientes/', views.api_recordatorios_pendientes, name='api_recordatorios_pendientes'),
]

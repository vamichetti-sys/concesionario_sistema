from django.contrib import admin
from .models import Proyecto, Tarea, Recordatorio


# ==========================================================
# Mixin: limita el queryset a las filas del propio usuario
# salvo que sea superuser. Sirve para los 3 modelos.
# ==========================================================
class UsuarioFilterMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(usuario=request.user)


@admin.register(Proyecto)
class ProyectoAdmin(UsuarioFilterMixin, admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'activo', 'color', 'created_at')
    list_filter = ('activo', 'usuario', 'created_at')
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('created_at',)
    ordering = ('-activo', '-created_at')


@admin.register(Tarea)
class TareaAdmin(UsuarioFilterMixin, admin.ModelAdmin):
    list_display = (
        'titulo', 'proyecto', 'estado', 'prioridad',
        'deadline', 'usuario', 'created_at',
    )
    list_filter = ('estado', 'prioridad', 'proyecto', 'usuario')
    search_fields = ('titulo', 'descripcion')
    autocomplete_fields = ('proyecto',)
    readonly_fields = ('created_at', 'completada_en')
    date_hierarchy = 'deadline'


@admin.register(Recordatorio)
class RecordatorioAdmin(UsuarioFilterMixin, admin.ModelAdmin):
    list_display = ('titulo', 'fecha_hora', 'tarea', 'notificado', 'usuario')
    list_filter = ('notificado', 'usuario')
    search_fields = ('titulo',)
    autocomplete_fields = ('tarea',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'fecha_hora'

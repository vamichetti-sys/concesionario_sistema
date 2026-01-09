from django.apps import AppConfig


class GestoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestoria'

    def ready(self):
        try:
            import gestoria.signals
        except ImportError:
            pass

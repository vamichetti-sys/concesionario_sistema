from django.apps import AppConfig


class VehiculosConfig(AppConfig):
    name = 'vehiculos'

    def ready(self):
        import vehiculos.signals  # noqa: F401

from django.apps import AppConfig


class ReportesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reportes"
    verbose_name = "Reportes"

    def ready(self):
        # Activa las signals del módulo Reportes
        import reportes.signals

from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cuentas'

    # ⚠️ DESACTIVADO TEMPORALMENTE
    # def ready(self):
    #     import cuentas.signals

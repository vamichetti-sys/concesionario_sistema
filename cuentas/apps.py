from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cuentas'

    # ⚠️ SEÑALES DESACTIVADAS A PROPÓSITO.
    # El recálculo de saldo se hace por llamadas explícitas a
    # recalcular_saldo() (que es idempotente). Ver cuentas/signals.py para
    # los pasos a seguir si en el futuro se activan señales (hay que quitar
    # las llamadas manuales para evitar doble recálculo).
    # def ready(self):
    #     import cuentas.signals

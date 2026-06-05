# cuentas/signals.py
#
# ARQUITECTURA DE RECÁLCULO (leer antes de activar señales)
# ----------------------------------------------------------
# Hoy el recálculo de saldo/estado de la cuenta NO usa señales: se dispara
# explícitamente llamando a `CuentaCorriente.recalcular_saldo()` desde:
#   - PlanPago.save()            (al crear un plan)
#   - PagoCuota.save()           (al aplicar un pago a una cuota)
#   - PlanPago.verificar_finalizacion()
#   - las vistas (registrar_movimiento, eliminar_pago, etc.)
#
# `recalcular_saldo()` es IDEMPOTENTE: recalcula el saldo desde cero sumando
# todos los movimientos (debe/haber). Llamarlo de más no rompe nada, solo
# repite trabajo. Por eso hoy NO hay riesgo de "doble recálculo" con valores
# incorrectos; en el peor caso hay una consulta de más.
#
# SI EN EL FUTURO SE ACTIVAN SEÑALES (post_save/post_delete de MovimientoCuenta
# o PagoCuota para recalcular automáticamente):
#   1) Activar `ready()` en cuentas/apps.py (importa este módulo).
#   2) QUITAR las llamadas manuales a recalcular_saldo() de los save()/vistas
#      para no recalcular dos veces (correcto pero más lento).
#   3) Conectar acá los handlers, por ejemplo:
#
#        from django.db.models.signals import post_save, post_delete
#        from django.dispatch import receiver
#        from .models import MovimientoCuenta
#
#        @receiver([post_save, post_delete], sender=MovimientoCuenta)
#        def _recalcular(sender, instance, **kwargs):
#            instance.cuenta.recalcular_saldo()
#
# Mientras tanto este módulo queda intencionalmente vacío.

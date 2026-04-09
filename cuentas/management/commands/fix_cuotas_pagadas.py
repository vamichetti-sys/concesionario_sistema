from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from cuentas.models import CuotaPlan, CuentaCorriente, Pago, PagoCuota


class Command(BaseCommand):
    help = "Marca como pagadas las cuotas pendientes que ya tienen saldo 0, y vincula pagos sueltos a cuotas"

    def handle(self, *args, **options):
        # Paso 1: Marcar cuotas con saldo 0 como pagadas
        cuotas = CuotaPlan.objects.filter(estado="pendiente")
        count_marcadas = 0
        for cuota in cuotas:
            if cuota.saldo_pendiente <= 0:
                cuota.estado = "pagada"
                cuota.save(update_fields=["estado"])
                count_marcadas += 1
                self.stdout.write(f"  Cuota #{cuota.numero} del plan {cuota.plan_id} marcada como pagada")

        # Paso 2: Para cuentas con cuotas pendientes y pagos no vinculados,
        # vincular automáticamente
        count_vinculados = 0
        cuentas = CuentaCorriente.objects.filter(
            plan_pago__cuotas__estado="pendiente"
        ).distinct()

        for cuenta in cuentas:
            plan = cuenta.plan_pago
            # Total ya aplicado via PagoCuota
            total_aplicado = (
                PagoCuota.objects.filter(cuota__plan=plan)
                .aggregate(t=Sum("monto_aplicado"))["t"]
                or Decimal("0")
            )
            # Total pagos (haber) en la cuenta
            total_haber = (
                cuenta.movimientos.filter(tipo="haber")
                .aggregate(t=Sum("monto"))["t"]
                or Decimal("0")
            )
            # Pagos no vinculados = haber - aplicado
            sin_vincular = total_haber - total_aplicado
            if sin_vincular <= 0:
                continue

            # Crear un PagoCuota "ficticio" para vincular el monto suelto
            pago = cuenta.pagos.order_by("-fecha").first()
            if not pago:
                continue

            restante = sin_vincular
            for cuota in plan.cuotas.filter(estado="pendiente").order_by("numero"):
                if restante <= 0:
                    break
                saldo = cuota.saldo_pendiente
                if saldo <= 0:
                    continue
                aplicar = min(restante, saldo)
                PagoCuota.objects.create(
                    pago=pago,
                    cuota=cuota,
                    monto_aplicado=aplicar,
                )
                cuota.marcar_pagada()
                restante -= aplicar
                count_vinculados += 1
                self.stdout.write(
                    f"  Vinculado ${aplicar} a cuota #{cuota.numero} "
                    f"del plan {plan.id} (cuenta {cuenta.id})"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {count_marcadas} cuotas marcadas, {count_vinculados} pagos vinculados"
        ))

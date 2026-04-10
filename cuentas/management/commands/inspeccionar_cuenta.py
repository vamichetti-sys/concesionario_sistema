from django.core.management.base import BaseCommand
from cuentas.models import CuentaCorriente


class Command(BaseCommand):
    help = "Lista todos los movimientos y pagos de una cuenta específica"

    def add_arguments(self, parser):
        parser.add_argument("cuenta_id", type=int)

    def handle(self, *args, **options):
        cuenta_id = options["cuenta_id"]
        try:
            c = CuentaCorriente.objects.get(id=cuenta_id)
        except CuentaCorriente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No existe cuenta #{cuenta_id}"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n=== Cuenta #{c.id} - {c.cliente} ==="))
        self.stdout.write(f"Estado: {c.estado} | Saldo BD: ${c.saldo}")
        if c.venta:
            v = c.venta
            self.stdout.write(f"Venta #{v.id} - Vehículo: {v.vehiculo}")

        self.stdout.write("\n--- TODOS LOS MOVIMIENTOS ---")
        for m in c.movimientos.all().order_by('fecha'):
            desc = (m.descripcion or "")[:70]
            self.stdout.write(
                f"  [{m.id}] {m.fecha:%d/%m/%Y %H:%M} | "
                f"tipo={m.tipo} | origen={m.origen} | "
                f"${m.monto} | {desc}"
            )

        self.stdout.write("\n--- TODOS LOS PAGOS (modelo Pago) ---")
        for p in c.pagos.all().order_by('fecha'):
            obs = (p.observaciones or "")[:50]
            self.stdout.write(
                f"  [{p.id}] {p.fecha:%d/%m/%Y %H:%M} | "
                f"recibo={p.numero_recibo} | "
                f"forma={p.forma_pago} | ${p.monto_total} | {obs}"
            )

        # Plan de pago
        plan = getattr(c, "plan_pago", None)
        if plan:
            self.stdout.write(f"\n--- PLAN DE PAGO #{plan.id} ({plan.estado}) ---")
            self.stdout.write(f"  Cantidad cuotas: {plan.cantidad_cuotas} | Monto cuota: ${plan.monto_cuota}")
            for cuota in plan.cuotas.all().order_by('numero'):
                self.stdout.write(
                    f"  Cuota {cuota.numero}: vto {cuota.vencimiento:%d/%m/%Y} | "
                    f"monto ${cuota.monto} | pagado ${cuota.total_pagado} | "
                    f"saldo ${cuota.saldo_pendiente} | estado {cuota.estado}"
                )

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from cuentas.models import CuentaCorriente, MovimientoCuenta


class Command(BaseCommand):
    help = "Diagnostica las cuentas con deuda de gestoría: lista los movimientos debe/haber"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cuenta",
            type=int,
            help="ID de cuenta corriente específica",
            default=None,
        )

    def handle(self, *args, **options):
        cuenta_id = options.get("cuenta")

        if cuenta_id:
            cuentas = CuentaCorriente.objects.filter(id=cuenta_id)
        else:
            # Cuentas con movimientos de gestoría
            cuentas = CuentaCorriente.objects.filter(
                movimientos__origen="gestoria"
            ).distinct()

        for cuenta in cuentas:
            mov_debe = cuenta.movimientos.filter(origen="gestoria", tipo="debe")
            mov_haber = cuenta.movimientos.filter(origen="gestoria", tipo="haber")

            total_debe = mov_debe.aggregate(t=Sum("monto"))["t"] or Decimal("0")
            total_haber = mov_haber.aggregate(t=Sum("monto"))["t"] or Decimal("0")
            saldo = total_debe - total_haber

            if saldo == 0:
                continue

            self.stdout.write(self.style.WARNING(
                f"\nCuenta #{cuenta.id} - {cuenta.cliente}"
            ))
            self.stdout.write(f"  Debes ({mov_debe.count()}):")
            for m in mov_debe:
                self.stdout.write(f"    [ID {m.id}] {m.fecha:%d/%m/%Y} - ${m.monto} - {m.descripcion}")
            self.stdout.write(f"  Haberes ({mov_haber.count()}):")
            for m in mov_haber:
                self.stdout.write(f"    [ID {m.id}] {m.fecha:%d/%m/%Y} - ${m.monto} - {m.descripcion}")
            self.stdout.write(f"  TOTAL DEBE: ${total_debe}")
            self.stdout.write(f"  TOTAL HABER: ${total_haber}")
            self.stdout.write(self.style.ERROR(f"  SALDO PENDIENTE: ${saldo}"))

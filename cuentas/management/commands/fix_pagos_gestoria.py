from django.core.management.base import BaseCommand
from cuentas.models import MovimientoCuenta


class Command(BaseCommand):
    help = "Corrige movimientos de pago de gestoría que quedaron con origen='manual' cuando deberían ser 'gestoria'"

    def handle(self, *args, **options):
        # Buscar movimientos haber con descripción que contiene "gestoría"
        # pero con origen distinto a "gestoria"
        movimientos = MovimientoCuenta.objects.filter(
            tipo="haber",
            descripcion__icontains="gestor",
        ).exclude(origen="gestoria")

        count = 0
        for m in movimientos:
            self.stdout.write(
                f"  [{m.id}] {m.fecha:%d/%m/%Y} cuenta #{m.cuenta_id} - "
                f"${m.monto} - {m.descripcion[:60]} (origen viejo: {m.origen})"
            )
            m.origen = "gestoria"
            m.save(update_fields=["origen"])
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nListo: {count} movimientos corregidos a origen=gestoria"
        ))

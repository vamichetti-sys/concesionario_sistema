from django.core.management.base import BaseCommand
from cuentas.models import CuotaPlan


class Command(BaseCommand):
    help = "Marca como pagadas las cuotas pendientes que ya tienen saldo 0"

    def handle(self, *args, **options):
        cuotas = CuotaPlan.objects.filter(estado="pendiente")
        count = 0
        for cuota in cuotas:
            if cuota.saldo_pendiente <= 0:
                cuota.estado = "pagada"
                cuota.save(update_fields=["estado"])
                count += 1
                self.stdout.write(f"  Cuota #{cuota.numero} del plan {cuota.plan_id} marcada como pagada")

        self.stdout.write(self.style.SUCCESS(f"Listo: {count} cuotas corregidas"))

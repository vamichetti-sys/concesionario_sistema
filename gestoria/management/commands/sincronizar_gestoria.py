from django.core.management.base import BaseCommand
from ventas.models import Venta
from gestoria.models import GestoriaTransferencia


class Command(BaseCommand):
    help = 'Sincroniza Gestoría desde ventas (sin duplicar)'

    def handle(self, *args, **kwargs):

        ventas = Venta.objects.filter(
            cliente__isnull=False,
            vehiculo__estado='vendido'
        )

        creados = 0
        actualizados = 0

        for venta in ventas:
            gestoria, created = GestoriaTransferencia.objects.get_or_create(
                vehiculo=venta.vehiculo,
                defaults={
                    'cliente': venta.cliente
                }
            )

            # 🔹 Si ya existía, sincronizamos cliente
            if not created and gestoria.cliente != venta.cliente:
                gestoria.cliente = venta.cliente
                gestoria.save(update_fields=['cliente'])
                actualizados += 1

            if created:
                creados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Gestoría sincronizada | Creados: {creados} | Actualizados: {actualizados}'
            )
        )

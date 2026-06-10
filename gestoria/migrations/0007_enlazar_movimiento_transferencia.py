from django.db import migrations


def enlazar(apps, schema_editor):
    """
    Enlaza cada gestoría existente con el MovimientoCuenta (debe, origen
    'gestoria') que ya había creado, para poder actualizarlo/revertirlo.
    Match por cuenta de la venta + vehículo.
    """
    Gestoria = apps.get_model("gestoria", "Gestoria")
    MovimientoCuenta = apps.get_model("cuentas", "MovimientoCuenta")

    for g in Gestoria.objects.filter(venta__isnull=False):
        if g.movimiento_transferencia_id:
            continue
        venta = g.venta
        cuenta = getattr(venta, "cuenta_corriente", None)
        if cuenta is None:
            continue
        mov = (
            MovimientoCuenta.objects
            .filter(cuenta=cuenta, origen="gestoria", tipo="debe", vehiculo_id=g.vehiculo_id)
            .order_by("id")
            .first()
        )
        if mov is not None:
            g.movimiento_transferencia_id = mov.id
            g.save(update_fields=["movimiento_transferencia"])


def revertir(apps, schema_editor):
    Gestoria = apps.get_model("gestoria", "Gestoria")
    Gestoria.objects.update(movimiento_transferencia=None)


class Migration(migrations.Migration):

    dependencies = [
        ("gestoria", "0006_gestoria_movimiento_transferencia"),
    ]

    operations = [
        migrations.RunPython(enlazar, revertir),
    ]

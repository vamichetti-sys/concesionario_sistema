# Generated manually – sincroniza retroactivamente FichaVehicular.vendedor
# con CompraVentaOperacion para que los vehículos aparezcan en la pantalla
# de Unidades del proveedor sin necesidad de re-guardar cada ficha.

from django.db import migrations


def _sync_vendedores(apps, schema_editor):
    FichaVehicular = apps.get_model("vehiculos", "FichaVehicular")
    CompraVentaOperacion = apps.get_model("compraventa", "CompraVentaOperacion")

    ORIGEN_PROVEEDOR = "proveedor"
    ESTADO_PENDIENTE = "pendiente"

    fichas = FichaVehicular.objects.filter(
        vendedor__isnull=False,
        vehiculo__isnull=False,
    ).only("id", "vendedor_id", "vehiculo_id")

    creadas = 0
    actualizadas = 0

    for f in fichas.iterator():
        op = CompraVentaOperacion.objects.filter(vehiculo_id=f.vehiculo_id).first()
        if op is None:
            CompraVentaOperacion.objects.create(
                vehiculo_id=f.vehiculo_id,
                proveedor_id=f.vendedor_id,
                origen=ORIGEN_PROVEEDOR,
                estado=ESTADO_PENDIENTE,
            )
            creadas += 1
        else:
            cambios = []
            if op.proveedor_id != f.vendedor_id:
                op.proveedor_id = f.vendedor_id
                cambios.append("proveedor")
            if op.origen != ORIGEN_PROVEEDOR:
                op.origen = ORIGEN_PROVEEDOR
                cambios.append("origen")
            if cambios:
                op.save(update_fields=cambios)
                actualizadas += 1

    print(f"[sync_vendedor] operaciones creadas={creadas} actualizadas={actualizadas}")


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("vehiculos", "0020_fichavehicular_informe_and_more"),
        ("compraventa", "0005_alter_compraventaoperacion_proveedor_and_more"),
    ]

    operations = [
        migrations.RunPython(_sync_vendedores, reverse_code=_noop),
    ]

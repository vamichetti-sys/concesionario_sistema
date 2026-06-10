from decimal import Decimal

from django.db import migrations


# gc_* (gasto concesionario) <-> gasto de ingreso correspondiente.
# La copia automática (ya eliminada) ponía gc_X = gasto_X. Limpiamos solo donde
# coinciden exactamente (la huella de esa copia) y borramos su espejo en
# Gastos Mensuales (tag [GCF:gc_X#<ficha_pk>]).
PARES = [
    ("gc_vtv", "gasto_vtv"),
    ("gc_verificacion", "gasto_verificacion"),
    ("gc_grabado_autopartes", "gasto_autopartes"),
]


def limpiar(apps, schema_editor):
    FichaVehicular = apps.get_model("vehiculos", "FichaVehicular")
    GastoMensual = apps.get_model("gastos_mensuales", "GastoMensual")

    for ficha in FichaVehicular.objects.all():
        cambios = []
        for gc_campo, ing_campo in PARES:
            gc_val = getattr(ficha, gc_campo, None) or Decimal("0")
            ing_val = getattr(ficha, ing_campo, None) or Decimal("0")
            if gc_val > 0 and gc_val == ing_val:
                setattr(ficha, gc_campo, Decimal("0"))
                cambios.append(gc_campo)
                tag = f"[GCF:{gc_campo}#{ficha.pk}]"
                GastoMensual.objects.filter(descripcion__contains=tag).delete()
        if cambios:
            ficha.save(update_fields=cambios)


def revertir(apps, schema_editor):
    # No se puede deshacer (no guardamos los valores previos).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("vehiculos", "0030_alter_vehiculo_estado"),
        ("gastos_mensuales", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(limpiar, revertir),
    ]

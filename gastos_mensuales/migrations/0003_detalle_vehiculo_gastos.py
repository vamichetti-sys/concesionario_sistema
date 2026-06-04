import re
from django.db import migrations


def backfill_descripciones(apps, schema_editor):
    """
    Actualiza los gastos de vehículos ya cargados para que el detalle
    muestre marca + modelo + (dominio) en vez de solo la marca.
    Identifica cada gasto por su tag [GCF:campo#fichaPk].
    """
    GastoMensual = apps.get_model("gastos_mensuales", "GastoMensual")
    FichaVehicular = apps.get_model("vehiculos", "FichaVehicular")

    patron = re.compile(r"\[GCF:[^\]]*#(\d+)\]")

    for g in GastoMensual.objects.filter(descripcion__contains="[GCF:"):
        m = patron.search(g.descripcion or "")
        if not m:
            continue
        try:
            ficha = FichaVehicular.objects.get(pk=int(m.group(1)))
        except FichaVehicular.DoesNotExist:
            continue
        veh = ficha.vehiculo
        ident = " ".join(
            str(x) for x in [getattr(veh, "marca", ""), getattr(veh, "modelo", "")] if x
        ).strip()
        dominio = getattr(veh, "dominio", "") or ""
        if dominio:
            ident = f"{ident} ({dominio})".strip() if ident else str(dominio)
        if not ident:
            continue
        tag = m.group(0)
        label = (g.descripcion or "").split(" – ")[0]
        nueva = f"{label} – {ident} {tag}"
        if nueva != g.descripcion:
            g.descripcion = nueva
            g.save(update_fields=["descripcion"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gastos_mensuales", "0002_ingresomensual"),
        ("vehiculos", "0022_remove_fichatecnica_abs_frenos_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_descripciones, noop),
    ]

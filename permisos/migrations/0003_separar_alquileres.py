from django.db import migrations


def grant_alquileres(apps, schema_editor):
    """
    Alquileres pasó a ser un permiso propio (antes estaba dentro de
    'cuentas_internas'). A quien ya tenía 'cuentas_internas' le agregamos
    'alquileres' para que no pierda el acceso.
    """
    PermisoUsuario = apps.get_model("permisos", "PermisoUsuario")
    for perm in PermisoUsuario.objects.all():
        claves = list(perm.claves or [])
        if "cuentas_internas" in claves and "alquileres" not in claves:
            claves.append("alquileres")
            perm.claves = claves
            perm.save(update_fields=["claves"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("permisos", "0002_permisos_granulares"),
    ]

    operations = [
        migrations.RunPython(grant_alquileres, noop),
    ]

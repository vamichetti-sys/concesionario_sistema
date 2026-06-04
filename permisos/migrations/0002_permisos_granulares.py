from django.db import migrations, models


# Mapeo de las 4 secciones viejas -> ítems equivalentes del nuevo sistema.
# Sirve para que los usuarios existentes conserven el acceso que ya tenían.
SECCION_A_ITEMS = {
    "operaciones": ["vehiculos", "compraventa", "ventas", "boletos"],
    "clientes": ["clientes", "cuentas_corrientes", "crm", "reventa"],
    "documentacion": ["gestoria", "documentacion", "deudas"],
    "administracion": ["facturacion", "agenda_pagos", "agenda_ingresos", "asistencia", "calendario"],
}


def poblar_claves(apps, schema_editor):
    PermisoUsuario = apps.get_model("permisos", "PermisoUsuario")
    for perm in PermisoUsuario.objects.all():
        claves = []
        for seccion, items in SECCION_A_ITEMS.items():
            if getattr(perm, seccion, False):
                claves.extend(items)
        perm.claves = claves
        perm.save(update_fields=["claves"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("permisos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="permisousuario",
            name="claves",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(poblar_claves, noop),
        migrations.RemoveField(model_name="permisousuario", name="operaciones"),
        migrations.RemoveField(model_name="permisousuario", name="clientes"),
        migrations.RemoveField(model_name="permisousuario", name="documentacion"),
        migrations.RemoveField(model_name="permisousuario", name="administracion"),
    ]

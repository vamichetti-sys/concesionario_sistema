from django.db import migrations


# Sugerencia de ente inicial según el concepto del gasto.
ENTE_SUGERIDO = {
    "f08": "Registro",
    "informes": "Registro",
    "patentes": "Patentes / Rentas",
    "infracciones": "Infracciones",
    "verificacion": "Verificación policial",
    "autopartes": "Grabado de autopartes",
    "vtv": "VTV",
    "r541": "R-541",
    "firmas": "Escribanía",
}


def poblar(apps, schema_editor):
    """
    Convierte los PagoGastoIngreso existentes al nuevo esquema:
      - pertenece: 'proveedor' si la ficha del vehículo tiene proveedor
        (vendedor), si no 'cliente'.
      - situacion: los que tenían mantiene_deuda_vehiculo=True pasan a
        'cli_concesion' (deuda impaga por concesionario, no saldado); el resto
        se asume saldado ('cli_directo' / 'prov_directo').
      - ente: sugerencia según el concepto, si estaba vacío.
    """
    Pago = apps.get_model("vehiculos", "PagoGastoIngreso")

    for p in Pago.objects.select_related("vehiculo").all():
        tiene_prov = False
        try:
            ficha = p.vehiculo.ficha
            tiene_prov = ficha.vendedor_id is not None
        except Exception:
            tiene_prov = False

        if tiene_prov:
            p.pertenece = "proveedor"
            p.situacion = "prov_directo"
            p.saldado = True
        else:
            p.pertenece = "cliente"
            if p.mantiene_deuda_vehiculo:
                p.situacion = "cli_concesion"
                p.saldado = False
            else:
                p.situacion = "cli_directo"
                p.saldado = True

        if not p.ente:
            p.ente = ENTE_SUGERIDO.get((p.concepto or "").lower(), "")

        p.save(update_fields=["pertenece", "situacion", "saldado", "ente"])


def revertir(apps, schema_editor):
    # No-op: los campos nuevos quedan con sus valores (la migración de esquema
    # de reversa los elimina si se desarma todo).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("vehiculos", "0027_pagogastoingreso_ente_pagogastoingreso_fecha_saldado_and_more"),
    ]

    operations = [
        migrations.RunPython(poblar, revertir),
    ]

from django.db import migrations


def reasignar_a_creador(apps, schema_editor):
    """Los gastos/ingresos personales que nacieron de la agenda quedaron
    asignados a quien EJECUTÓ el pago/cobro (pagado_por/cobrado_por). El dueño
    que los agendó dejó de verlos. Acá los devolvemos a quien los agendó
    (creado_por), que es el comportamiento correcto a partir de ahora.
    """
    PagoFuturo = apps.get_model("agenda_pagos", "PagoFuturo")
    GastoPersonal = apps.get_model("gastos_personales", "GastoPersonal")
    for pago in PagoFuturo.objects.exclude(gasto_personal_id=None).exclude(creado_por=None):
        GastoPersonal.objects.filter(pk=pago.gasto_personal_id).exclude(
            usuario_id=pago.creado_por_id
        ).update(usuario_id=pago.creado_por_id)

    try:
        IngresoFuturo = apps.get_model("agenda_ingresos", "IngresoFuturo")
        IngresoPersonal = apps.get_model("gastos_personales", "IngresoPersonal")
    except LookupError:
        return
    for ing in IngresoFuturo.objects.exclude(ingreso_personal_id=None).exclude(creado_por=None):
        IngresoPersonal.objects.filter(pk=ing.ingreso_personal_id).exclude(
            usuario_id=ing.creado_por_id
        ).update(usuario_id=ing.creado_por_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gastos_personales", "0004_ingresopersonal_pago_alquiler"),
        ("agenda_pagos", "0007_alter_pagofuturo_destino"),
        ("agenda_ingresos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reasignar_a_creador, noop),
    ]

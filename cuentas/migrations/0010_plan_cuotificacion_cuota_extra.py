from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0009_cuentacorriente_observaciones"),
    ]

    operations = [
        migrations.AddField(
            model_name="planpago",
            name="cuotificacion",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Monto sobre el cual se calculan las cuotas. Si queda en 0 se usa (financiado − anticipo).",
                max_digits=14,
                verbose_name="Cuotificación (monto a cuotificar)",
            ),
        ),
        migrations.AddField(
            model_name="planpago",
            name="cuota_extra",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Si se carga, se agrega una cuota adicional con este importe al final del plan.",
                max_digits=14,
                verbose_name="Cuota extra",
            ),
        ),
    ]

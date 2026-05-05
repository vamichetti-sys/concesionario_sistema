from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0008_movimientocuenta_pago"),
    ]

    operations = [
        migrations.AddField(
            model_name="cuentacorriente",
            name="observaciones",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Notas internas sobre el cliente / cuenta",
            ),
        ),
    ]

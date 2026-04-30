from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cuentas", "0007_alter_cuentacorriente_venta"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimientocuenta",
            name="pago",
            field=models.ForeignKey(
                blank=True,
                help_text="Pago que originó este movimiento (si aplica)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="movimientos_creados",
                to="cuentas.pago",
            ),
        ),
    ]

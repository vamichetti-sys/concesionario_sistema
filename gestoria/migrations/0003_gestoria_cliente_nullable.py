from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0001_initial"),
        ("gestoria", "0002_alter_gestoria_cliente_alter_gestoria_vehiculo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gestoria",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="clientes.cliente",
            ),
        ),
    ]

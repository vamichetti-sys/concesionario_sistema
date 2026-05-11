from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("boletos", "0009_entregadocumentacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="reserva",
            name="permuta2_marca",
            field=models.CharField(blank=True, max_length=100, verbose_name="Marca (usado 2)"),
        ),
        migrations.AddField(
            model_name="reserva",
            name="permuta2_patente",
            field=models.CharField(blank=True, max_length=20, verbose_name="Patente (usado 2)"),
        ),
        migrations.AddField(
            model_name="reserva",
            name="permuta2_suma",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=15,
                null=True,
                verbose_name="Suma propuesta (usado 2)",
            ),
        ),
    ]

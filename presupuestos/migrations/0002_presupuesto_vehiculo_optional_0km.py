from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vehiculos", "0001_initial"),
        ("presupuestos", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="presupuesto",
            name="vehiculo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="presupuestos",
                to="vehiculos.vehiculo",
            ),
        ),
        migrations.AddField(
            model_name="presupuesto",
            name="es_0km",
            field=models.BooleanField(default=False, verbose_name="Es 0km"),
        ),
        migrations.AddField(
            model_name="presupuesto",
            name="vehiculo_descripcion",
            field=models.CharField(
                blank=True,
                help_text="Marca / Modelo / Versión cuando el vehículo no está en stock.",
                max_length=255,
                verbose_name="Descripción del vehículo",
            ),
        ),
        migrations.AddField(
            model_name="presupuesto",
            name="vehiculo_anio",
            field=models.CharField(blank=True, max_length=10, verbose_name="Año"),
        ),
        migrations.AddField(
            model_name="presupuesto",
            name="vehiculo_color",
            field=models.CharField(blank=True, max_length=80, verbose_name="Color"),
        ),
    ]

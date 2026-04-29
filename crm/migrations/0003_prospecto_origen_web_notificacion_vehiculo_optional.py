from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vehiculos", "0001_initial"),
        ("crm", "0002_notificacioncrm"),
    ]

    operations = [
        migrations.AlterField(
            model_name="prospecto",
            name="origen",
            field=models.CharField(
                choices=[
                    ("whatsapp", "WhatsApp"),
                    ("telefono", "Teléfono"),
                    ("presencial", "Presencial"),
                    ("instagram", "Instagram"),
                    ("facebook", "Facebook"),
                    ("mercadolibre", "MercadoLibre"),
                    ("referido", "Referido"),
                    ("web", "Formulario web"),
                    ("otro", "Otro"),
                ],
                default="whatsapp",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="notificacioncrm",
            name="vehiculo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notificaciones_crm",
                to="vehiculos.vehiculo",
            ),
        ),
    ]

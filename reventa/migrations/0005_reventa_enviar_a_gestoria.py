from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reventa", "0004_reventa_documentacion_entregada"),
    ]

    operations = [
        migrations.AddField(
            model_name="reventa",
            name="enviar_a_gestoria",
            field=models.BooleanField(
                default=False,
                verbose_name="Enviar a Gestoría al transferir",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="publicacionplataforma",
            name="plataforma",
            field=models.CharField(
                choices=[
                    ("mercadolibre", "Story"),
                    ("facebook", "Facebook Marketplace"),
                    ("instagram", "Instagram"),
                    ("web", "Página web"),
                ],
                max_length=20,
            ),
        ),
    ]

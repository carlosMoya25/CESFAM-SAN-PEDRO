from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("farmacia", "0006_movimientofarmacia_clave_salida_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimientofarmacia",
            name="destinatario",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("farmacia", "0005_stockpendientefarmacia"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimientofarmacia",
            name="documento_entrega",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="movimientofarmacia",
            name="clave_salida",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]

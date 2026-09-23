from django.db import migrations


TIPOS_MOVIMIENTO = [
    "Entrada",
    "Salida",
    "Transferencia",
    "Ajuste positivo",
    "Ajuste negativo",
]


def crear_tipos_movimiento(apps, schema_editor):
    TipoMovimiento = apps.get_model(
        "inventario",
        "TipoMovimiento",
    )

    for nombre in TIPOS_MOVIMIENTO:
        TipoMovimiento.objects.get_or_create(
            nombre=nombre
        )


def eliminar_tipos_movimiento(apps, schema_editor):
    TipoMovimiento = apps.get_model(
        "inventario",
        "TipoMovimiento",
    )

    TipoMovimiento.objects.filter(
        nombre__in=TIPOS_MOVIMIENTO
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            crear_tipos_movimiento,
            eliminar_tipos_movimiento,
        ),
    ]
from django.db import migrations


ROLES = [
    "Administrador",
    "Técnico TI",
    "Funcionario",
    "Encargado de Inventario",
    "Encargado de Farmacia",
]


def crear_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


def eliminar_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    Group.objects.filter(
        name__in=ROLES
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0002_alter_usuario_managers"),
    ]

    operations = [
        migrations.RunPython(
            crear_roles,
            eliminar_roles,
        ),
    ]
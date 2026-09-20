from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario

    list_display = (
        "email",
        "nombres",
        "apellido_paterno",
        "anexo",
        "departamento",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "groups",
        "anexo",
        "departamento",
    )

    search_fields = (
        "email",
        "nombres",
        "apellido_paterno",
        "apellido_materno",
    )

    ordering = ("apellido_paterno", "nombres")

    fieldsets = (
        (None, {
            "fields": ("email", "password")
        }),
        ("Información personal", {
            "fields": (
                "nombres",
                "apellido_paterno",
                "apellido_materno",
                "telefono",
                "anexo",
                "departamento",
            )
        }),
        ("Roles y permisos", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Fechas", {
            "fields": ("last_login", "date_joined")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "nombres",
                "apellido_paterno",
                "apellido_materno",
                "telefono",
                "anexo",
                "departamento",
                "password1",
                "password2",
                "is_active",
                "is_staff",
                "groups",
            ),
        }),
    )
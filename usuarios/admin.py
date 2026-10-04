from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, HistorialSeguridad


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

@admin.register(HistorialSeguridad)
class HistorialSeguridadAdmin(admin.ModelAdmin):

    list_display = (
        "fecha",
        "tipo_accion",
        "email_afectado",
        "realizado_por",
    )

    list_filter = (
        "tipo_accion",
        "fecha",
    )

    search_fields = (
        "email_afectado",
        "usuario_afectado__email",
        "realizado_por__email",
    )

    readonly_fields = (
        "tipo_accion",
        "usuario_afectado",
        "email_afectado",
        "realizado_por",
        "descripcion",
        "fecha",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
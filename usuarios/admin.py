from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, HistorialSeguridad

from django import forms
from django.contrib.auth.models import Group

from organizacion.models import Anexo, Departamento


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


class UsuarioAdminForm(forms.ModelForm):

    roles = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="Roles del usuario",
    )

    class Meta:
        model = Usuario

        fields = [
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "email",
            "telefono",
            "anexo",
            "departamento",
            "is_active",
        ]

        labels = {
            "nombres": "Nombres",
            "apellido_paterno": "Apellido paterno",
            "apellido_materno": "Apellido materno",
            "email": "Correo electrónico",
            "telefono": "Teléfono",
            "anexo": "Anexo",
            "departamento": "Departamento",
            "is_active": "Usuario activo",
        }

        widgets = {
            "nombres": forms.TextInput(
                attrs={"placeholder": "Ej: Juan Carlos"}
            ),

            "apellido_paterno": forms.TextInput(
                attrs={"placeholder": "Ej: Pérez"}
            ),

            "apellido_materno": forms.TextInput(
                attrs={"placeholder": "Ej: González"}
            ),

            "email": forms.EmailInput(
                attrs={"placeholder": "usuario@institucion.cl"}
            ),

            "telefono": forms.TextInput(
                attrs={"placeholder": "Ej: +56 9 1234 5678"}
            ),

            "anexo": forms.Select(),

            "departamento": forms.Select(),

            "is_active": forms.CheckboxInput(),
        }


    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["roles"].queryset = Group.objects.order_by("name")

        self.fields["anexo"].queryset = (
            Anexo.objects
            .filter(activo=True)
            .order_by("nombre")
        )

        self.fields["departamento"].queryset = (
            Departamento.objects
            .filter(activo=True)
            .order_by("nombre")
        )

        if self.instance.pk:

            self.fields["roles"].initial = (
                self.instance.groups.all()
            )


    def clean_email(self):

        email = self.cleaned_data["email"].strip().lower()

        usuarios = Usuario.objects.filter(
            email__iexact=email
        )

        if self.instance.pk:
            usuarios = usuarios.exclude(pk=self.instance.pk)

        if usuarios.exists():

            raise forms.ValidationError(
                "Ya existe un usuario registrado con este correo electrónico."
            )

        return email


    def save(self, commit=True):

        usuario = super().save(commit=False)

        usuario.email = self.cleaned_data["email"].lower()

        # Si se crea desde este panel, inicialmente puede
        # autenticarse mediante Google sin contraseña local.
        if not usuario.pk:
            usuario.set_unusable_password()

        if commit:

            usuario.save()

            usuario.groups.set(
                self.cleaned_data["roles"]
            )

        return usuario
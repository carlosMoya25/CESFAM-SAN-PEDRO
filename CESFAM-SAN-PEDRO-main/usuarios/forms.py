from copy import copy

from django import forms
from django.contrib.auth.models import Group

from organizacion.models import Anexo, Departamento
from .models import Usuario
from .claves import campos_clave_temporal, validar_clave_temporal


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
                attrs={
                    "placeholder": "Ej: Juan Carlos",
                }
            ),
            "apellido_paterno": forms.TextInput(
                attrs={
                    "placeholder": "Ej: Pérez",
                }
            ),
            "apellido_materno": forms.TextInput(
                attrs={
                    "placeholder": "Ej: González",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "usuario@institucion.cl",
                }
            ),
            "telefono": forms.TextInput(
                attrs={
                    "placeholder": "Ej: +56 9 1234 5678",
                }
            ),
            "anexo": forms.Select(),
            "departamento": forms.Select(),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, administrador=None, **kwargs):
        self.administrador = administrador
        self.advertencias_clave = []
        self.token_autorizacion = ""
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["modo_acceso"] = forms.ChoiceField(label="Forma de acceso", initial="google", choices=[
                ("google", "Mediante Google"), ("clave", "Con contraseña y Google"),
            ])
            self.fields.update(campos_clave_temporal())

        # Roles disponibles
        self.fields["roles"].queryset = Group.objects.order_by("name")

        # Solo anexos activos
        self.fields["anexo"].queryset = (
            Anexo.objects
            .filter(activo=True)
            .order_by("nombre")
        )

        # Solo departamentos activos
        self.fields["departamento"].queryset = (
            Departamento.objects
            .filter(activo=True)
            .order_by("nombre")
        )

        # Al editar, mostrar los roles actuales
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.groups.all()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        usuarios = Usuario.objects.filter(
            email__iexact=email
        )

        # Si estamos editando, excluir al propio usuario
        if self.instance.pk:
            usuarios = usuarios.exclude(pk=self.instance.pk)

        if usuarios.exists():
            raise forms.ValidationError(
                "Ya existe un usuario registrado con este correo electrónico."
            )

        return email

    def clean(self):
        datos = super().clean()
        if self.instance.pk and "is_active" in self.changed_data:
            self.add_error("is_active", "Para cambiar el estado utiliza la acción de activar o desactivar en el detalle del usuario.")
        if self.instance.pk and self.administrador and self.instance.pk == self.administrador.pk:
            if not self.administrador.is_superuser and not datos.get("roles", Group.objects.none()).filter(name="Administrador").exists():
                self.add_error("roles", "No puedes quitarte tu propio rol de administrador.")
        if self.instance.pk and self.instance.groups.filter(name="Técnico TI").exists():
            from .desvinculacion import pendientes_usuario
            if not datos.get("roles", Group.objects.none()).filter(name="Técnico TI").exists() and pendientes_usuario(self.instance).exists():
                self.add_error("roles", "Reasigna las solicitudes pendientes antes de retirar el rol Técnico TI; puedes usar la desactivación con reemplazo.")
        if not self.instance.pk and datos.get("modo_acceso") == "clave":
            candidato = copy(self.instance)
            for campo in ("email", "nombres", "apellido_paterno", "apellido_materno"):
                setattr(candidato, campo, datos.get(campo, ""))
            validar_clave_temporal(self, usuario=candidato, administrador=self.administrador)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)

        usuario.email = self.cleaned_data["email"].strip().lower()

        if not usuario.pk:
            if self.cleaned_data.get("modo_acceso") == "clave":
                usuario.set_password(self.cleaned_data["clave1"])
                usuario.debe_cambiar_clave = True
            else:
                usuario.set_unusable_password()

        if commit:
            usuario.save()

            # Permite uno o varios roles
            usuario.groups.set(
                self.cleaned_data["roles"]
            )

        return usuario


class DesvinculacionForm(forms.Form):
    reemplazo = forms.ModelChoiceField(queryset=Usuario.objects.none(), required=False,
                                      label="Técnico TI que recibirá las solicitudes pendientes")
    motivo = forms.CharField(max_length=500, label="Motivo administrativo",
                             help_text="No incluyas información clínica ni antecedentes sensibles.",
                             widget=forms.Textarea(attrs={"rows": 3}))
    confirmar = forms.BooleanField(label="Confirmo la desactivación de la cuenta y la revocación de sus sesiones.")

    def __init__(self, *args, usuario, tiene_pendientes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reemplazo"].queryset = Usuario.objects.filter(
            is_active=True, groups__name="Técnico TI").exclude(pk=usuario.pk).distinct()
        self.fields["reemplazo"].required = tiene_pendientes

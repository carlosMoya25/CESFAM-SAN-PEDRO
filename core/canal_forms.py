from django import forms
from django.contrib.auth import get_user_model


class ConfiguracionCanalForm(forms.Form):
    entidad = forms.CharField(max_length=200, label="Entidad responsable del tratamiento")
    contacto = forms.EmailField(label="Correo institucional de atención")
    validador = forms.ModelChoiceField(queryset=get_user_model().objects.none(), label="Persona que debe validar el contacto")
    autorizados = forms.ModelMultipleChoiceField(queryset=get_user_model().objects.none(),
        label="Personas autorizadas para consultar y responder solicitudes recibidas", widget=forms.CheckboxSelectMultiple)
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("validador", "autorizados"):
            self.fields[campo].queryset = get_user_model().objects.filter(is_active=True)


class ValidacionContactoForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    evidencia = forms.CharField(max_length=500, label="Cómo se verificó el contacto y su atención",
                               help_text="Registra el procedimiento o referencia institucional, sin credenciales ni datos sensibles.",
                               widget=forms.Textarea(attrs={"rows": 3}))
    confirmar = forms.BooleanField(label="Confirmo que verifiqué el contacto y su atención según el procedimiento institucional.")


class HabilitacionCanalForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    habilitar = forms.TypedChoiceField(choices=[("si", "Habilitar recepción"), ("no", "Suspender nuevas solicitudes")],
                                      coerce=lambda valor: valor == "si", label="Estado de recepción")
    confirmar = forms.BooleanField(label="Confirmo esta acción. Para habilitar, el CESFAM debe haber validado el canal, el procedimiento de identidad y la atención de solicitudes.")


class EnvioDerechoForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    confirmar = forms.BooleanField(label="Confirmo el envío de esta solicitud y elijo recibir su acuse y respuesta en esta cuenta del sistema.")


class RespuestaDerechoForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    identidad_verificada = forms.BooleanField(label="Verifiqué la identidad y la procedencia de la entrega de información según el procedimiento institucional.")
    verificacion = forms.CharField(max_length=500, label="Referencia del procedimiento de verificación",
                                  widget=forms.Textarea(attrs={"rows": 2}))
    respuesta = forms.CharField(max_length=10000, label="Respuesta al solicitante", widget=forms.Textarea(attrs={"rows": 8}),
                               help_text="Se publicará en su cuenta. Incluye los fundamentos y vías de reclamación que correspondan según el procedimiento institucional. No ingreses contraseñas, tokens ni datos de terceros.")
    confirmar = forms.BooleanField(label="Confirmo la publicación de esta respuesta definitiva en la cuenta del solicitante.")

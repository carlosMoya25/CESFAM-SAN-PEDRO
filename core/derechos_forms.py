from django import forms

from .models import SolicitudDerecho


class SolicitudDerechoForm(forms.ModelForm):
    clave_creacion = forms.UUIDField(widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = SolicitudDerecho
        fields = ["tipo", "detalle", "campo_rectificar", "valor_solicitado"]
        labels = {
            "tipo": "¿Qué quieres solicitar?",
            "detalle": "Describe tu solicitud",
            "campo_rectificar": "Dato que necesitas corregir",
            "valor_solicitado": "Valor que propones registrar",
        }
        help_texts = {
            "detalle": "Indica qué información sobre ti deseas consultar o corregir. Máximo 2.000 caracteres.",
            "campo_rectificar": "Solo para rectificación. Por ejemplo: teléfono o apellido.",
            "valor_solicitado": "Solo para rectificación. No ingreses contraseñas, datos clínicos ni datos de otras personas.",
        }
        widgets = {"detalle": forms.Textarea(attrs={"rows": 5}),
                   "campo_rectificar": forms.TextInput(attrs={"placeholder": "Ej.: teléfono"}),
                   "valor_solicitado": forms.TextInput(attrs={"autocomplete": "off"})}

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") == SolicitudDerecho.Tipo.RECTIFICACION:
            for campo in ("campo_rectificar", "valor_solicitado"):
                if not datos.get(campo):
                    self.add_error(campo, "Completa este campo para preparar una rectificación.")
        else:
            # No conservar valores de rectificación cuando se cambia a acceso.
            datos["campo_rectificar"] = ""
            datos["valor_solicitado"] = ""
        return datos

from django import forms
from django.contrib.auth import get_user_model


class ResponsablePrivacidadForm(forms.Form):
    responsable = forms.ModelChoiceField(queryset=get_user_model().objects.none(),
                                        label="Persona encargada de atender solicitudes de privacidad")
    motivo = forms.CharField(max_length=500, label="Motivo de la asignación o cambio",
                             help_text="No incluyas datos sensibles.", widget=forms.Textarea(attrs={"rows": 2}))
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = get_user_model().objects.filter(is_active=True)

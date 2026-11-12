from django import forms


class ReglaConservacionForm(forms.Form):
    dias = forms.IntegerField(required=False, min_value=1, max_value=36500,
                              label="Plazo propuesto en días",
                              help_text="Sin valor significa que el plazo aún no está definido. No se aplica un plazo legal automático.")
    fundamento = forms.CharField(required=False, max_length=1000, label="Fundamento o referencia institucional",
                                help_text="Indica la política, resolución o criterio a revisar por el CESFAM. No incluyas datos sensibles.",
                                widget=forms.Textarea(attrs={"rows": 4}))
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def clean(self):
        datos = super().clean()
        if datos.get("dias") is not None and not datos.get("fundamento"):
            self.add_error("fundamento", "Indica el fundamento de este plazo propuesto.")
        return datos

from django import forms

from organizacion.models import Anexo

from .models import Articulo, CategoriaArticulo

class EntradaInventarioForm(forms.Form):
    anexo = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        label="Anexo de destino",
    )

    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        label="Artículo",
    )

    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad",
    )

    motivo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class SalidaInventarioForm(forms.Form):
    anexo = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        label="Anexo de origen",
    )

    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        label="Artículo",
    )

    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad",
    )

    motivo = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class TransferenciaInventarioForm(forms.Form):
    anexo_origen = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        label="Anexo de origen",
    )

    anexo_destino = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        label="Anexo de destino",
    )

    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        label="Artículo",
    )

    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad",
    )

    motivo = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean(self):
        cleaned_data = super().clean()

        origen = cleaned_data.get("anexo_origen")
        destino = cleaned_data.get("anexo_destino")

        if origen and destino and origen == destino:
            raise forms.ValidationError(
                "El anexo de origen y destino deben ser diferentes."
            )

        return cleaned_data

class AjusteInventarioForm(forms.Form):

    TIPO_AJUSTE = [
        ("positivo", "Ajuste positivo"),
        ("negativo", "Ajuste negativo"),
    ]

    anexo = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        label="Anexo",
    )

    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        label="Artículo",
    )

    tipo_ajuste = forms.ChoiceField(
        choices=TIPO_AJUSTE,
        label="Tipo de ajuste",
    )

    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad a ajustar",
    )

    motivo = forms.CharField(
        required=True,
        label="Motivo del ajuste",
        widget=forms.Textarea(
            attrs={"rows": 3}
        ),
    )

class RecursoRequerimientoForm(forms.Form):

    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        label="Artículo utilizado",
    )

    cantidad = forms.IntegerField(
        min_value=1,
        label="Cantidad",
    )

class CategoriaArticuloForm(forms.ModelForm):
    class Meta:
        model = CategoriaArticulo
        fields = [
            "nombre",
            "descripcion",
            "activo",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ej: Equipos computacionales",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Descripción de la categoría",
                }
            ),
        }


class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = [
            "nombre",
            "descripcion",
            "categoria",
            "codigo",
            "stock_minimo",
            "activo",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ej: Mouse USB",
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Descripción del artículo",
                }
            ),
            "codigo": forms.TextInput(
                attrs={
                    "placeholder": "Ej: MOU-001",
                }
            ),
            "stock_minimo": forms.NumberInput(
                attrs={
                    "min": 0,
                }
            ),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo")

        if codigo:
            codigo = codigo.strip()

        return codigo or None
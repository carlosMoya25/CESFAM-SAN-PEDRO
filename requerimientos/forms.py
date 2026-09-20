from django import forms
from .models import Requerimiento


class RequerimientoForm(forms.ModelForm):

    class Meta:
        model = Requerimiento

        fields = [
            "titulo",
            "descripcion",
            "anexo",
            "departamento",
            "tipo_requerimiento",
            "prioridad",
        ]

        widgets = {
            "titulo": forms.TextInput(
                attrs={"placeholder": "Ej: Computador no enciende"}
            ),

            "descripcion": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Describe el problema..."
                }
            ),
        }

class ResolverRequerimientoForm(forms.Form):
    solucion = forms.CharField(
        label="Solución aplicada",
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Describe la solución aplicada al requerimiento..."
                ),
            }
        ),
    )


class ObservacionRequerimientoForm(forms.Form):
    observacion = forms.CharField(
        label="Observación",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Escribe una observación sobre la atención...",
            }
        ),
    )
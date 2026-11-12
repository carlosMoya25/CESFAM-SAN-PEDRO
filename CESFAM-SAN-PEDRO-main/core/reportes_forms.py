from datetime import timedelta

from django import forms
from django.utils import timezone

from organizacion.models import Anexo

from .reportes import DIAS_RANGO_POR_DEFECTO, rango_por_defecto


class FiltroReporteForm(forms.Form):
    """Filtro de fecha y ubicación común a los 4 paneles de reportes y a los PDF."""

    desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    ubicacion = forms.ModelChoiceField(
        queryset=Anexo.objects.filter(activo=True),
        required=False,
        label="Ubicación",
        empty_label="Todas las ubicaciones",
    )

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and desde > (hasta or timezone.localdate()):
            self.add_error("hasta", "La fecha final debe ser igual o posterior a la inicial.")
        return datos

    def rango(self):
        """(desde, hasta) ya resueltos: aplica el rango por defecto si no se filtró por fecha."""
        if not self.is_valid():
            return rango_por_defecto()

        desde = self.cleaned_data.get("desde")
        hasta = self.cleaned_data.get("hasta")

        if not desde and not hasta:
            return rango_por_defecto()

        if not hasta:
            hasta = timezone.localdate()
        if not desde:
            desde = hasta - timedelta(days=DIAS_RANGO_POR_DEFECTO - 1)

        return desde, hasta

    def ubicacion_seleccionada(self):
        if not self.is_valid():
            return None
        return self.cleaned_data.get("ubicacion")

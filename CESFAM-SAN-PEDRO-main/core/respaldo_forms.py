from django import forms
from django.contrib.auth import get_user_model

from .models import PoliticaRespaldos


DIAS_SEMANA = [(0, "Lunes"), (1, "Martes"), (2, "Miércoles"), (3, "Jueves"),
               (4, "Viernes"), (5, "Sábado"), (6, "Domingo")]


class ProgramacionRespaldosForm(forms.Form):
    accion = forms.ChoiceField(choices=[("activar", "Activar"), ("suspender", "Suspender")], widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    politica_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    motivo = forms.CharField(max_length=1000, label="Motivo de la activación o suspensión",
                             widget=forms.Textarea(attrs={"rows": 2}))
    confirmar = forms.BooleanField(label="Confirmo el cambio de programación. Las copias seguirán requiriendo prueba de recuperación y traslado a Windows.")


class PoliticaRespaldosForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    motivo = forms.CharField(max_length=1000, label="Motivo o referencia institucional del cambio",
                             widget=forms.Textarea(attrs={"rows": 2}))
    dia_semana = forms.TypedChoiceField(choices=[("", "Sin definir"), *DIAS_SEMANA], required=False,
                                        coerce=int, empty_value=None, label="Día de la semana",
                                        help_text="Se aplica a la frecuencia semanal. La selección se conserva si cambias de frecuencia.")

    class Meta:
        model = PoliticaRespaldos
        fields = ["frecuencia", "hora", "dia_semana", "copias_diarias", "copias_semanales",
                  "copias_mensuales", "prueba_cada_dias", "custodio", "suplente", "procedimiento_clave",
                  "ubicacion", "proteccion_adicional"]
        labels = {
            "frecuencia": "Frecuencia prevista", "hora": "Hora prevista (Chile continental)",
            "copias_diarias": "Copias diarias que se conservarán", "copias_semanales": "Copias semanales que se conservarán",
            "copias_mensuales": "Copias mensuales que se conservarán", "prueba_cada_dias": "Probar recuperación cada cuántos días",
            "custodio": "Custodio principal de la clave", "suplente": "Suplente del custodio",
            "procedimiento_clave": "Procedimiento de custodia de la clave",
            "ubicacion": "Ubicación del servidor Windows respecto de la aplicación",
            "proteccion_adicional": "Plan de protección ante pérdida de la ubicación",
        }
        widgets = {
            "hora": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "procedimiento_clave": forms.Textarea(attrs={"rows": 3}),
            "proteccion_adicional": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "frecuencia": "Manual no genera copias automáticas. Para programarlas, selecciona Diariamente, Cada 12 horas o Semanalmente.",
            "hora": "Para cada 12 horas, indica la primera ejecución; la segunda será 12 horas después.",
            "procedimiento_clave": "Describe cómo recuperar la clave y la referencia del procedimiento. No ingreses la clave, contraseñas ni códigos de acceso.",
            "proteccion_adicional": "Indica cómo se conservará una copia separada del lugar físico y quién verificará su recuperación. Documentar un plan no acredita su ejecución.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        activos = get_user_model().objects.filter(is_active=True).order_by("email")
        for nombre in ("custodio", "suplente"):
            self.fields[nombre].queryset = activos
        for nombre, maximo in (("copias_diarias", 365), ("copias_semanales", 104), ("copias_mensuales", 120)):
            self.fields[nombre].min_value = 0
            self.fields[nombre].max_value = maximo
            self.fields[nombre].widget.attrs.update({"min": 0, "max": maximo})
        self.fields["prueba_cada_dias"].widget.attrs.update({"min": 1, "max": 365})

    def clean(self):
        datos = super().clean()
        frecuencia = datos.get("frecuencia")
        if frecuencia in ("DIARIA", "DOCE_HORAS", "SEMANAL") and not datos.get("hora"):
            self.add_error("hora", "Indica la hora prevista para esta frecuencia.")
        if frecuencia == "SEMANAL" and datos.get("dia_semana") is None:
            self.add_error("dia_semana", "Selecciona el día de la semana.")
        for nombre, maximo in (("copias_diarias", 365), ("copias_semanales", 104), ("copias_mensuales", 120)):
            valor = datos.get(nombre)
            if valor is not None and not 0 <= valor <= maximo:
                self.add_error(nombre, f"Ingresa una cantidad entre 0 y {maximo}.")
        dias = datos.get("prueba_cada_dias")
        if dias is not None and not 1 <= dias <= 365:
            self.add_error("prueba_cada_dias", "Ingresa un plazo entre 1 y 365 días.")
        if datos.get("custodio") and datos.get("custodio") == datos.get("suplente"):
            self.add_error("suplente", "El suplente debe ser una persona distinta del custodio principal.")
        if datos.get("ubicacion") == "MISMA" and not datos.get("proteccion_adicional"):
            self.add_error("proteccion_adicional", "Define el plan para proteger una copia frente a la pérdida de ese lugar.")
        return datos

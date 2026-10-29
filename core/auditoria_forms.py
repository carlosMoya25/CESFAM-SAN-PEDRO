from datetime import date

from django import forms
from django.contrib.auth import get_user_model

from .models import EventoAuditoria


class FiltrosAuditoriaForm(forms.Form):
    desde = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hasta = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    usuario = forms.ModelChoiceField(required=False, label="Usuario", queryset=get_user_model().objects.order_by("email"), empty_label="Todos")
    modulo = forms.ChoiceField(required=False, label="Módulo", choices=[("", "Todos")] + [(m, m.capitalize()) for m in (
        "usuarios", "requerimientos", "inventario", "farmacia", "organizacion", "privacidad", "respaldos", "core", "admin", "auth", "account", "socialaccount")])
    accion = forms.ChoiceField(required=False, label="Acción", choices=[("", "Todas")] + [(a, a.replace("_", " ").capitalize()) for a in (
        "CREAR", "MODIFICAR", "ELIMINAR", "CONSULTAR", "SOLICITUD_HTTP", "CAMBIAR_ROLES", "CAMBIAR_PERMISOS", "CAMBIAR_AUTORIZADOS",
        "INICIO_SESION", "FIN_SESION", "ACCESO_FALLIDO", "BLOQUEO", "COMANDO_INICIADO", "COMANDO_FINALIZADO")])
    resultado = forms.ChoiceField(required=False, label="Resultado", choices=[("", "Todos"), *EventoAuditoria.Resultado.choices])
    modelo = forms.RegexField(r"^[a-z][a-z0-9_.]+$", required=False, max_length=100, label="Modelo", help_text="Ejemplo: inventario.articulo")
    objeto_id = forms.CharField(required=False, max_length=100, label="ID del registro")
    solicitud_id = forms.UUIDField(required=False, label="Referencia de seguimiento")

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if hasta == date.max:
            self.add_error("hasta", "Selecciona una fecha final anterior al año 10000.")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        return datos

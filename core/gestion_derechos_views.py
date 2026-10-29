from core.auditoria import marcar_formulario, marcar_rechazo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .canal_forms import RespuestaDerechoForm
from .canal_privacidad import puede_responder
from .derechos_services import responder_solicitud
from .models import SolicitudDerecho


@never_cache
@login_required
@require_GET
def bandeja_derechos(request):
    if not puede_responder(request.user):
        return HttpResponseForbidden()
    solicitudes = SolicitudDerecho.objects.exclude(estado="BORRADOR").exclude(solicitante=request.user).select_related("solicitante")
    estado = request.GET.get("estado", "RECIBIDA")
    if estado not in ("RECIBIDA", "RESPONDIDA", "TODAS"):
        estado = "RECIBIDA"
    if estado != "TODAS":
        solicitudes = solicitudes.filter(estado=estado)
    pagina = Paginator(solicitudes, 20).get_page(request.GET.get("pagina"))
    return render(request, "core/derechos/bandeja.html", {"solicitudes": pagina, "estado_filtro": estado,
                                                         "hoy": timezone.localdate()})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def gestionar_derecho(request, identificador):
    if not puede_responder(request.user):
        return HttpResponseForbidden()
    solicitud = get_object_or_404(SolicitudDerecho.objects.select_related("solicitante", "respondida_por"),
                                 identificador=identificador, estado__in=["RECIBIDA", "RESPONDIDA"])
    if solicitud.solicitante_id == request.user.pk:
        return HttpResponseForbidden()
    form = RespuestaDerechoForm(request.POST if request.method == "POST" else None,
                               initial={"revision": solicitud.revision})
    if request.method == "POST" and form.is_valid():
        try:
            responder_solicitud(usuario=request.user, identificador=identificador, datos=form.cleaned_data)
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, "Respuesta publicada en la cuenta del solicitante.")
            return redirect("gestionar_derecho", identificador=identificador)
    marcar_formulario(form)
    return render(request, "core/derechos/gestionar.html", {"solicitud": solicitud, "form": form})

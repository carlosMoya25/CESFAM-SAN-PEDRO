from core.auditoria import marcar_formulario, marcar_rechazo
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.http import require_POST

from .derechos_forms import SolicitudDerechoForm
from .derechos_services import guardar_borrador, enviar_solicitud
from .canal_forms import EnvioDerechoForm
from .canal_privacidad import configuracion_actual, canal_disponible
from .models import SolicitudDerecho


def contexto_canal():
    cfg = configuracion_actual()
    return {"canal_disponible": canal_disponible(cfg), "cfg_canal": cfg}


@never_cache
@login_required
@require_GET
def mis_derechos(request):
    solicitudes = SolicitudDerecho.objects.filter(solicitante=request.user)
    pagina = Paginator(solicitudes, 10).get_page(request.GET.get("pagina"))
    return render(request, "core/derechos/lista.html", {"solicitudes": pagina, **contexto_canal()})


@never_cache
@login_required
@require_GET
def detalle_derecho(request, identificador):
    solicitud = get_object_or_404(SolicitudDerecho, identificador=identificador, solicitante=request.user)
    return render(request, "core/derechos/detalle.html", {"solicitud": solicitud,
        "form_envio": EnvioDerechoForm(initial={"revision": solicitud.revision}), **contexto_canal()})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def formulario_derecho(request, identificador=None):
    solicitud = None
    if identificador:
        solicitud = get_object_or_404(SolicitudDerecho, identificador=identificador, solicitante=request.user,
                                     estado="BORRADOR")
    inicial = {"clave_creacion": solicitud.clave_creacion if solicitud else uuid.uuid4(),
               "revision": solicitud.revision if solicitud else 0}
    form = SolicitudDerechoForm(request.POST if request.method == "POST" else None,
                               instance=solicitud, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            solicitud = guardar_borrador(usuario=request.user, datos=form.cleaned_data,
                                         identificador=identificador)
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, "Borrador guardado. Todavía no se ha enviado a atención institucional.")
            return redirect("detalle_derecho", identificador=solicitud.identificador)
    marcar_formulario(form)
    return render(request, "core/derechos/formulario.html", {"form": form, "solicitud": solicitud, **contexto_canal()})


@never_cache
@login_required
@require_POST
def enviar_derecho(request, identificador):
    # Resolver la propiedad antes de validar el formulario para no revelar solicitudes ajenas.
    get_object_or_404(SolicitudDerecho, identificador=identificador, solicitante=request.user)
    form = EnvioDerechoForm(request.POST)
    if form.is_valid():
        try:
            enviar_solicitud(usuario=request.user, identificador=identificador, revision=form.cleaned_data["revision"])
        except ValidationError as exc:
            marcar_rechazo()
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Solicitud recibida. El acuse y el seguimiento están disponibles en tu cuenta.")
    else:
        marcar_rechazo()
        messages.error(request, "Confirma el envío y el medio de respuesta antes de continuar.")
    return redirect("detalle_derecho", identificador=identificador)

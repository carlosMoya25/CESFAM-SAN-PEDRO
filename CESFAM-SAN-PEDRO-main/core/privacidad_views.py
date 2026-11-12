from core.auditoria import marcar_rechazo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import privacidad
from .models import ConstanciaPrivacidad, ConfiguracionPrivacidad, HistorialResponsablePrivacidad
from .privacidad_forms import ResponsablePrivacidadForm
from .privacidad_services import asignar_responsable
from .canal_privacidad import puede_configurar, puede_responder
from usuarios.utils import es_administrador, es_tecnico


def contexto(request, error="", form_responsable=None):
    constancia = None
    puede_ver_constancias = (
        request.user.is_authenticated
        and request.user.is_active
        and (es_administrador(request.user) or es_tecnico(request.user))
    )
    constancias = None
    puede_asignar_responsable = es_administrador(request.user)
    configuracion = None
    historial_responsable = None
    if request.user.is_authenticated:
        configuracion = ConfiguracionPrivacidad.objects.select_related("responsable").filter(pk=1).first()
        constancia = ConstanciaPrivacidad.objects.filter(
            usuario=request.user, version=privacidad.VERSION, huella=privacidad.HUELLA,
        ).first()
    if puede_ver_constancias:
        registros = ConstanciaPrivacidad.objects.select_related("usuario").order_by("-fecha", "-pk")
        constancias = Paginator(registros, 20).get_page(request.GET.get("pagina_constancias"))
    if puede_asignar_responsable:
        if form_responsable is None:
            form_responsable = ResponsablePrivacidadForm(initial={
                "responsable": configuracion.responsable_id if configuracion else None,
                "revision": configuracion.revision if configuracion else 0,
            })
        historial_responsable = HistorialResponsablePrivacidad.objects.select_related(
            "anterior", "nuevo", "administrador")[:10]
    return {
        "base_privacidad": "base.html" if request.user.is_authenticated else "base_login.html",
        "aviso": privacidad, "constancia": constancia, "error": error,
        "puede_ver_constancias": puede_ver_constancias,
        "constancias": constancias,
        "configuracion_privacidad": configuracion,
        "puede_asignar_responsable": puede_asignar_responsable,
        "form_responsable": form_responsable,
        "historial_responsable": historial_responsable,
        "puede_ver_panel": puede_configurar(request.user, configuracion) if request.user.is_authenticated else False,
        "puede_atender_derechos": puede_responder(request.user, configuracion) if request.user.is_authenticated else False,
    }


@never_cache
@require_GET
def aviso_privacidad(request):
    return render(request, "core/privacidad.html", contexto(request))


@never_cache
@login_required
@require_POST
def confirmar_privacidad(request):
    error = ""
    if request.POST.get("version") != privacidad.VERSION or request.POST.get("huella") != privacidad.HUELLA:
        error = "El aviso cambió. Revisa la versión que se muestra y vuelve a confirmar su lectura."
    elif request.POST.get("lectura") != "si":
        error = "Marca la casilla de lectura si deseas registrar tu constancia."
    if error:
        return render(request, "core/privacidad.html", contexto(request, error), status=400)
    ConstanciaPrivacidad.objects.get_or_create(
        usuario=request.user, version=privacidad.VERSION, huella=privacidad.HUELLA,
        defaults={"texto": privacidad.TEXTO, "declaracion": privacidad.DECLARACION},
    )
    messages.success(request, "Tu constancia de lectura quedó registrada.")
    return redirect("aviso_privacidad")


@never_cache
@login_required
@require_POST
def cambiar_responsable_privacidad(request):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    form = ResponsablePrivacidadForm(request.POST)
    if form.is_valid():
        try:
            asignar_responsable(administrador=request.user, responsable_id=form.cleaned_data["responsable"].pk,
                               motivo=form.cleaned_data["motivo"], revision=form.cleaned_data["revision"])
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, "Responsable de atención de privacidad actualizado.")
            return redirect(f"{reverse('aviso_privacidad')}#responsable-privacidad")
    return render(request, "core/privacidad.html", contexto(request, form_responsable=form), status=400)

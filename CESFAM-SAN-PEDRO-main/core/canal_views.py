from core.auditoria import marcar_formulario, marcar_rechazo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from usuarios.utils import es_administrador
from .canal_forms import ConfiguracionCanalForm, HabilitacionCanalForm, ValidacionContactoForm
from .canal_privacidad import (cambiar_habilitacion, configuracion_actual, guardar_configuracion,
                              puede_configurar, validar_contacto, canal_disponible)
from .models import HistorialCanalPrivacidad


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def panel_institucional(request):
    cfg = configuracion_actual()
    if not puede_configurar(request.user, cfg):
        return HttpResponseForbidden()
    admin = es_administrador(request.user)
    es_validador = bool(cfg and cfg.validador_id == request.user.pk)
    revision = cfg.revision if cfg else 0
    inicial = {"revision": revision, "entidad": cfg.entidad if cfg else "", "contacto": cfg.contacto if cfg else "",
               "validador": cfg.validador_id if cfg else None,
               "autorizados": list(cfg.autorizados.values_list("pk", flat=True)) if cfg else []}
    form_configuracion = ConfiguracionCanalForm(initial=inicial, auto_id="config_%s") if admin else None
    form_validacion = ValidacionContactoForm(initial={"revision": revision}, auto_id="validacion_%s") if es_validador else None
    form_habilitacion = HabilitacionCanalForm(initial={"revision": revision, "habilitar": "no"}, auto_id="canal_%s") if admin else None
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "configurar" and admin:
            form = form_configuracion = ConfiguracionCanalForm(request.POST, auto_id="config_%s")
            operacion = lambda datos: guardar_configuracion(usuario=request.user, datos=datos)
        elif accion == "validar" and es_validador:
            form = form_validacion = ValidacionContactoForm(request.POST, auto_id="validacion_%s")
            operacion = lambda datos: validar_contacto(usuario=request.user, revision=datos["revision"], evidencia=datos["evidencia"])
        elif accion == "habilitar" and admin:
            form = form_habilitacion = HabilitacionCanalForm(request.POST, auto_id="canal_%s")
            operacion = lambda datos: cambiar_habilitacion(usuario=request.user, revision=datos["revision"], habilitar=datos["habilitar"])
        else:
            return HttpResponseForbidden()
        if form.is_valid():
            try:
                operacion(form.cleaned_data)
            except ValidationError as exc:
                marcar_rechazo()
                form.add_error(None, exc)
            else:
                messages.success(request, "Cambio institucional registrado en el historial.")
                return redirect("panel_institucional")
    if request.method == "POST":
        marcar_formulario(form)
    historial = HistorialCanalPrivacidad.objects.select_related("realizado_por")[:20] if admin else None
    return render(request, "core/derechos/panel_institucional.html", {
        "cfg": cfg, "canal_disponible": canal_disponible(cfg), "es_admin": admin,
        "form_configuracion": form_configuracion, "form_validacion": form_validacion,
        "form_habilitacion": form_habilitacion, "historial_canal": historial,
    })

from core.auditoria import marcar_formulario, marcar_rechazo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from usuarios.utils import es_administrador
from .conservacion import CRITERIOS, guardar_regla, simular_conservacion, tablas_reglas
from .conservacion_forms import ReglaConservacionForm
from .models import ReglaConservacion, SimulacionConservacion


@never_cache
@login_required
@require_GET
def panel_conservacion(request):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    informes = SimulacionConservacion.objects.select_related("realizado_por")
    return render(request, "core/conservacion/panel.html", {
        "reglas": tablas_reglas(), "informes": Paginator(informes, 10).get_page(request.GET.get("pagina"))})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def editar_regla_conservacion(request, categoria):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    if categoria not in CRITERIOS:
        raise Http404
    regla = ReglaConservacion.objects.filter(categoria=categoria).first()
    inicial = {"dias": regla.dias if regla else None, "fundamento": regla.fundamento if regla else "",
               "revision": regla.revision if regla else 0}
    form = ReglaConservacionForm(request.POST if request.method == "POST" else None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            guardar_regla(usuario=request.user, categoria=categoria, **form.cleaned_data)
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, "Propuesta registrada. No se modificaron ni eliminaron los datos evaluados.")
            return redirect("panel_conservacion")
    marcar_formulario(form)
    return render(request, "core/conservacion/regla.html", {"form": form, "regla": regla,
        "nombre": ReglaConservacion.Categoria(categoria).label, "criterio": CRITERIOS[categoria]})


@never_cache
@login_required
@require_POST
def ejecutar_simulacion_conservacion(request):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    try:
        informe = simular_conservacion(usuario=request.user)
    except ValidationError as exc:
        marcar_rechazo()
        messages.error(request, " ".join(exc.messages))
        return redirect("panel_conservacion")
    return redirect("detalle_simulacion_conservacion", pk=informe.pk)


@never_cache
@login_required
@require_GET
def detalle_simulacion_conservacion(request, pk):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    informe = get_object_or_404(SimulacionConservacion.objects.select_related("realizado_por"), pk=pk)
    return render(request, "core/conservacion/informe.html", {"informe": informe})

from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from usuarios.utils import puede_ver_auditoria
from .auditoria_forms import FiltrosAuditoriaForm
from .models import EventoAuditoria


@never_cache
@login_required
@require_GET
def panel_auditoria(request):
    if not puede_ver_auditoria(request.user):
        return HttpResponseForbidden()
    form = FiltrosAuditoriaForm(request.GET)
    eventos = EventoAuditoria.objects.select_related("usuario")
    if form.is_valid():
        for campo in ("usuario", "modulo", "accion", "resultado", "modelo", "objeto_id", "solicitud_id"):
            if form.cleaned_data.get(campo):
                eventos = eventos.filter(**{campo: form.cleaned_data[campo]})
        if form.cleaned_data["desde"]:
            eventos = eventos.filter(fecha__gte=timezone.make_aware(datetime.combine(form.cleaned_data["desde"], time.min)))
        if form.cleaned_data["hasta"]:
            siguiente = form.cleaned_data["hasta"] + timedelta(days=1)
            eventos = eventos.filter(fecha__lt=timezone.make_aware(datetime.combine(siguiente, time.min)))
    else:
        eventos = eventos.none()
    pagina = Paginator(eventos, 25).get_page(request.GET.get("page"))
    filtros = request.GET.copy()
    filtros.pop("page", None)
    return render(request, "core/auditoria/panel.html", {
        "form": form, "eventos": pagina, "pagina": pagina, "filtros_query": filtros.urlencode(),
    })


@never_cache
@login_required
@require_GET
def detalle_auditoria(request, pk):
    if not puede_ver_auditoria(request.user):
        return HttpResponseForbidden()
    evento = get_object_or_404(EventoAuditoria.objects.select_related("usuario"), pk=pk)
    campos = [(campo, evento.antes.get(campo), evento.despues.get(campo), campo in evento.antes or campo in evento.despues)
              for campo in evento.campos]
    return render(request, "core/auditoria/detalle.html", {"evento": evento, "campos": campos})

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.pdf_views import reporte_pdf_apartado
from core.reportes import datos_requerimientos
from core.reportes_forms import FiltroReporteForm
from usuarios.utils import es_administrador, es_tecnico

LIMITE_LISTADO = 50


@login_required
def panel_reportes(request):
    """Vista de reportes de Soporte TI: pendientes, en atención, resueltas y gráficos."""
    if not es_tecnico(request.user) and not es_administrador(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder a los reportes de Soporte TI."
        )

    form = FiltroReporteForm(request.GET or None)
    desde, hasta = form.rango()
    ubicacion = form.ubicacion_seleccionada()

    datos = datos_requerimientos(desde, hasta, ubicacion)
    formato = request.GET.get("pdf")
    if formato in ("resumen", "detallado"):
        return reporte_pdf_apartado(
            request, formato, "ti", "Requerimientos", datos, desde, hasta, ubicacion,
        )
    datos["listado"] = datos["listado"][:LIMITE_LISTADO]

    context = {
        "form": form,
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "puede_ti": True,
        "datos": datos,
        "limite_listado": LIMITE_LISTADO,
    }
    return render(request, "requerimientos/reportes.html", context)

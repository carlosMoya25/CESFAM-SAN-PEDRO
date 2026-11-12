from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.pdf_views import reporte_pdf_apartado
from core.reportes import datos_insumos
from core.reportes_forms import FiltroReporteForm
from usuarios.utils import puede_gestionar_inventario

LIMITE_LISTADO = 50


@login_required
def panel_reportes(request):
    """Vista de reportes de Insumos: artículos que requieren re-stock y movimiento."""
    if not puede_gestionar_inventario(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder a los reportes de Insumos."
        )

    form = FiltroReporteForm(request.GET or None)
    desde, hasta = form.rango()
    ubicacion = form.ubicacion_seleccionada()

    datos = datos_insumos(desde, hasta, ubicacion)
    formato = request.GET.get("pdf")
    if formato in ("resumen", "detallado"):
        return reporte_pdf_apartado(
            request, formato, "insumos", "Artículos", datos, desde, hasta, ubicacion,
        )
    datos["stock_bajo"] = datos["stock_bajo"][:LIMITE_LISTADO]
    datos["sin_stock"] = datos["sin_stock"][:LIMITE_LISTADO]

    context = {
        "form": form,
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "datos": datos,
        "limite_listado": LIMITE_LISTADO,
    }
    return render(request, "inventario/reportes.html", context)

from django.shortcuts import render

from core.pdf_views import reporte_pdf_apartado
from core.reportes import datos_farmacia
from core.reportes_forms import FiltroReporteForm

from .decorators import acceso_farmacia

LIMITE_LISTADO = 50


@acceso_farmacia
def panel_reportes(request):
    """Vista de reportes de Farmacia: lotes por vencer/vencidos y movimiento."""
    form = FiltroReporteForm(request.GET or None)
    desde, hasta = form.rango()
    ubicacion = form.ubicacion_seleccionada()

    datos = datos_farmacia(desde, hasta, ubicacion)
    formato = request.GET.get("pdf")
    if formato in ("resumen", "detallado"):
        return reporte_pdf_apartado(
            request, formato, "farmacia", "Farmacia", datos, desde, hasta, ubicacion,
        )
    datos["lotes_por_vencer"] = datos["lotes_por_vencer"][:LIMITE_LISTADO]
    datos["lotes_vencidos"] = datos["lotes_vencidos"][:LIMITE_LISTADO]

    context = {
        "form": form,
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "datos": datos,
        "limite_listado": LIMITE_LISTADO,
    }
    return render(request, "farmacia/reportes.html", context)

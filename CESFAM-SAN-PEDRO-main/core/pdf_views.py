from django.contrib.auth.decorators import login_required
from django.utils import timezone

from usuarios.utils import (
    es_administrador,
    es_tecnico,
    puede_gestionar_farmacia,
    puede_gestionar_inventario,
)

from .pdf_utils import render_pdf
from .reportes import datos_farmacia, datos_insumos, datos_requerimientos
from .reportes_forms import FiltroReporteForm

LIMITE_DETALLE = 200


def _contexto_informe(request):
    form = FiltroReporteForm(request.GET or None)
    desde, hasta = form.rango()
    ubicacion = form.ubicacion_seleccionada()

    puede_ti = es_tecnico(request.user) or es_administrador(request.user)
    puede_insumos = puede_gestionar_inventario(request.user)
    puede_farmacia = puede_gestionar_farmacia(request.user)

    contexto = {
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "generado_en": timezone.localtime(),
        "usuario": request.user,
        "puede_ti": puede_ti,
        "puede_insumos": puede_insumos,
        "puede_farmacia": puede_farmacia,
    }

    if puede_ti:
        contexto["ti"] = datos_requerimientos(desde, hasta, ubicacion)
    if puede_insumos:
        contexto["insumos"] = datos_insumos(desde, hasta, ubicacion)
    if puede_farmacia:
        contexto["farmacia"] = datos_farmacia(desde, hasta, ubicacion)

    return contexto


@login_required
def reporte_pdf_resumen(request):
    contexto = _contexto_informe(request)
    nombre = f"sigri_resumen_{contexto['desde']}_{contexto['hasta']}.pdf"
    return render_pdf("core/pdf/reporte_resumen.html", contexto, nombre)


@login_required
def reporte_pdf_detallado(request):
    contexto = _contexto_informe(request)

    if contexto.get("ti"):
        contexto["ti"]["listado"] = contexto["ti"]["listado"][:LIMITE_DETALLE]
    if contexto.get("insumos"):
        contexto["insumos"]["stock_bajo"] = contexto["insumos"]["stock_bajo"][:LIMITE_DETALLE]
        contexto["insumos"]["sin_stock"] = contexto["insumos"]["sin_stock"][:LIMITE_DETALLE]
    if contexto.get("farmacia"):
        contexto["farmacia"]["lotes_por_vencer"] = contexto["farmacia"]["lotes_por_vencer"][:LIMITE_DETALLE]
        contexto["farmacia"]["lotes_vencidos"] = contexto["farmacia"]["lotes_vencidos"][:LIMITE_DETALLE]

    nombre = f"sigri_detallado_{contexto['desde']}_{contexto['hasta']}.pdf"
    return render_pdf("core/pdf/reporte_detallado.html", contexto, nombre)


def reporte_pdf_apartado(request, formato, seccion, apartado, datos, desde, hasta, ubicacion):
    """Genera el PDF desde un panel que ya validó el permiso del usuario."""
    contexto = {
        "apartado": apartado,
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "generado_en": timezone.localtime(),
        "usuario": request.user,
        f"puede_{seccion}": True,
        seccion: datos,
    }
    return render_pdf(
        f"core/pdf/reporte_{formato}.html",
        contexto,
        f"sigri_{seccion}_{formato}_{desde}_{hasta}.pdf",
        descargar=True,
    )

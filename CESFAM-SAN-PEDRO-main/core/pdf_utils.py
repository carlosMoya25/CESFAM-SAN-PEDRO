"""
Renderizado de informes institucionales en PDF a partir de templates HTML,
usando xhtml2pdf (no requiere dependencias de sistema adicionales al
Dockerfile actual).
"""
import os

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def _resolver_recursos(uri, rel):
    """link_callback de xhtml2pdf: traduce una URL estática a una ruta de archivo real."""
    if uri.startswith(settings.STATIC_URL):
        ruta_relativa = uri[len(settings.STATIC_URL):]

        candidatos = [os.path.join(settings.BASE_DIR, "static", ruta_relativa)]
        static_root = getattr(settings, "STATIC_ROOT", None)
        if static_root:
            candidatos.append(os.path.join(static_root, ruta_relativa))

        for candidato in candidatos:
            if os.path.isfile(candidato):
                return candidato

    return uri


def render_pdf(template_name, context, nombre_archivo, descargar=False):
    """Renderiza ``template_name`` a PDF y lo entrega como HttpResponse."""
    html = render_to_string(template_name, context)

    respuesta = HttpResponse(content_type="application/pdf")
    disposicion = "attachment" if descargar else "inline"
    respuesta["Content-Disposition"] = f'{disposicion}; filename="{nombre_archivo}"'

    resultado = pisa.CreatePDF(
        src=html,
        dest=respuesta,
        link_callback=_resolver_recursos,
        encoding="utf-8",
    )

    if resultado.err:
        return HttpResponse(
            "No fue posible generar el informe en PDF. "
            "Contacta al administrador del sistema si el problema persiste.",
            status=500,
        )

    return respuesta

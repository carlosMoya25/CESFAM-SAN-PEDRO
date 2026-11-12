from core.auditoria import marcar_formulario, marcar_rechazo
from pathlib import Path
import hashlib
import tempfile
import zipfile

from django.conf import settings
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from usuarios.utils import es_administrador, es_tecnico
from .models import (CambioPoliticaRespaldos, CambioProgramacionRespaldos, DescargaRespaldo,
                     EjecucionProgramadaRespaldo, PoliticaRespaldos, ProgramacionRespaldos, RespaldoBase)
from .respaldo_crypto import ErrorRespaldo, leer_clave, leer_manifiesto, rutas
from .respaldo_forms import DIAS_SEMANA, PoliticaRespaldosForm, ProgramacionRespaldosForm
from .respaldo_politica import guardar_politica, pendientes_politica
from .respaldo_programacion import cambiar_programacion, ejecutor_disponible, proximo_turno
from django.utils import timezone


def puede_ver_respaldos(usuario):
    return es_administrador(usuario) or es_tecnico(usuario)


def preparar_copia(copia):
    path = Path(settings.BACKUP_ROOT) / f"{copia.pk.hex}.cesfam"
    copia.archivo_disponible = path.is_file() and not path.is_symlink()
    estado = copia.verificacion.get("estado")
    copia.estado_texto = {"OK": "Comprobada", "FALLIDA": "Prueba no completada"}.get(estado, "Pendiente")
    copia.estado_clase = {"OK": "success", "FALLIDA": "warning"}.get(estado, "neutral")
    return copia


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def panel_respaldos(request, form_programacion=None, errores_programacion=None):
    if not puede_ver_respaldos(request.user):
        return HttpResponseForbidden()
    politica = PoliticaRespaldos.objects.select_related("custodio", "suplente").filter(pk=1).first() or PoliticaRespaldos()
    es_post_politica = request.method == "POST" and form_programacion is None
    form = PoliticaRespaldosForm(request.POST if es_post_politica else None,
                                 instance=politica, initial={"revision": politica.revision})
    if es_post_politica and form.is_valid():
        try:
            guardar_politica(usuario=request.user, datos=form.cleaned_data)
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, "Política de respaldos registrada. No se activaron tareas automáticas ni se eliminaron copias.")
            return redirect(reverse("panel_respaldos") + "#politica-respaldos")
    # ModelForm puede modificar su instancia durante la validación; el resumen muestra solo lo guardado.
    politica = PoliticaRespaldos.objects.select_related("custodio", "suplente").filter(pk=1).first() or PoliticaRespaldos()
    registros = RespaldoBase.objects.prefetch_related("pruebas").order_by("-creado_at", "-pk")
    ultima = registros.first()
    if ultima:
        preparar_copia(ultima)
        registros = registros.exclude(pk=ultima.pk)
    pagina = Paginator(registros, 10).get_page(request.GET.get("pagina"))
    for copia in pagina:
        preparar_copia(copia)
    cambios = list(CambioPoliticaRespaldos.objects.select_related("realizado_por")[:10])
    for cambio in cambios:
        cambio.diferencias = [(form.fields[nombre].label, cambio.antes.get(nombre, "Sin definir"), cambio.despues.get(nombre, "Sin definir"))
                              for nombre in PoliticaRespaldosForm.Meta.fields if cambio.antes.get(nombre) != cambio.despues.get(nombre)]
    programacion = ProgramacionRespaldos.objects.filter(pk=1).first() or ProgramacionRespaldos()
    if form_programacion is None:
        form_programacion = ProgramacionRespaldosForm(initial={"revision": programacion.revision,
            "politica_revision": politica.revision, "accion": "suspender" if programacion.activa else "activar"})
    ejecuciones = list(EjecucionProgramadaRespaldo.objects.select_related("respaldo")[:10])
    marcar_formulario(form)
    return render(request, "core/respaldos/panel.html", {"copias": pagina, "ultima": ultima,
        "politica": politica, "form_politica": form, "pendientes_politica": pendientes_politica(politica),
        "dia_previsto": dict(DIAS_SEMANA).get(politica.dia_semana, "Sin definir"),
        "cambios_politica": cambios, "form_abierto": form.is_bound or not politica.revision,
        "programacion": programacion, "form_programacion": form_programacion,
        "errores_programacion": errores_programacion or [],
        "ejecutor_disponible": bool(settings.BACKUP_WORKER_ID and programacion.ejecutor == settings.BACKUP_WORKER_ID
                                    and ejecutor_disponible(programacion, timezone.now())),
        "ejecutor_configurado": bool(settings.BACKUP_WORKER_ID),
        "proxima_copia": proximo_turno(politica, timezone.now()) if programacion.activa else None,
        "ejecuciones": ejecuciones, "ultima_ejecucion": ejecuciones[0] if ejecuciones else None,
        "cambios_programacion": CambioProgramacionRespaldos.objects.select_related("realizado_por")[:10]})


@never_cache
@login_required
@require_POST
def configurar_programacion_respaldos(request):
    if not puede_ver_respaldos(request.user):
        return HttpResponseForbidden()
    form = ProgramacionRespaldosForm(request.POST)
    if form.is_valid():
        datos = form.cleaned_data
        try:
            programacion = cambiar_programacion(usuario=request.user, activar=datos["accion"] == "activar", revision=datos["revision"],
                politica_revision=datos["politica_revision"], motivo=datos["motivo"])
        except ValidationError as exc:
            marcar_rechazo()
            return panel_respaldos(request, form_programacion=form, errores_programacion=exc.messages)
        else:
            if datos["accion"] == "activar":
                disponible = bool(settings.BACKUP_WORKER_ID and programacion.ejecutor == settings.BACKUP_WORKER_ID
                    and ejecutor_disponible(programacion, timezone.now()))
                messages.success(request, "Programación activada." if disponible else
                    "Solicitud de activación guardada. Pendiente de preparar o conectar el ejecutor del servidor; todavía no se están generando copias automáticas.")
            else:
                messages.success(request, "Programación suspendida. Una copia ya iniciada puede terminar; no se iniciarán las siguientes.")
    else:
        marcar_rechazo()
        return panel_respaldos(request, form_programacion=form,
            errores_programacion=["No se cambió la programación. Revisa los campos indicados."])
    return redirect(reverse("panel_respaldos") + "#programacion-respaldos")


@never_cache
@login_required
@require_POST
def descargar_respaldo(request, identificador):
    if not puede_ver_respaldos(request.user):
        return HttpResponseForbidden()
    copia = get_object_or_404(RespaldoBase, pk=identificador)
    paquete = tempfile.TemporaryFile()
    try:
        root, _ = rutas()
        nombre = copia.pk.hex
        archivo = root / f"{nombre}.cesfam"
        manifiesto = root / f"{nombre}.json"
        if archivo.is_symlink() or not archivo.is_file():
            raise ErrorRespaldo("Archivo no disponible.")
        contenido_manifiesto = manifiesto.read_bytes() if not manifiesto.is_symlink() else b""
        datos = leer_manifiesto(manifiesto, leer_clave())
        if contenido_manifiesto != manifiesto.read_bytes():
            raise ErrorRespaldo("El manifiesto cambió durante la comprobación.")
        # Se verifica el contenido que efectivamente se incorpora al ZIP.
        digest = hashlib.sha256()
        total = 0
        with zipfile.ZipFile(paquete, "w", compression=zipfile.ZIP_STORED) as zip:
            with archivo.open("rb") as origen, zip.open(archivo.name, "w", force_zip64=True) as destino:
                for bloque in iter(lambda: origen.read(1024 * 1024), b""):
                    digest.update(bloque)
                    total += len(bloque)
                    destino.write(bloque)
            if digest.hexdigest() != copia.sha256 or datos.get("sha256") != copia.sha256 or total != copia.tamano:
                raise ErrorRespaldo("La copia no coincide con su registro.")
            zip.writestr(manifiesto.name, contenido_manifiesto)
        paquete.seek(0)
        with transaction.atomic():
            DescargaRespaldo.objects.create(respaldo=copia, usuario=request.user, sha256=copia.sha256)
        response = FileResponse(paquete, as_attachment=True, filename=f"respaldo-{nombre}.zip",
                                content_type="application/zip")
        response["X-Content-Type-Options"] = "nosniff"
        return response
    except (ErrorRespaldo, OSError):
        paquete.close()
        return HttpResponse("No se pudo preparar la copia. Revisa su disponibilidad e integridad con mantenimiento.", status=409)
    except Exception:
        paquete.close()
        raise


@never_cache
@login_required
@require_GET
def historial_descargas_respaldos(request):
    if not puede_ver_respaldos(request.user):
        return HttpResponseForbidden()
    registros = DescargaRespaldo.objects.select_related("usuario", "respaldo")
    pagina = Paginator(registros, 20).get_page(request.GET.get("pagina"))
    return render(request, "core/respaldos/historial.html", {"descargas": pagina})

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import EventoSolicitudDerecho, SolicitudDerecho


CAMPOS_BORRADOR = ("tipo", "detalle", "campo_rectificar", "valor_solicitado")


@transaction.atomic
def guardar_borrador(*, usuario, datos, identificador=None):
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied
    contenido = {campo: datos[campo] for campo in CAMPOS_BORRADOR}
    if identificador is None:
        if datos["revision"] != 0:
            raise ValidationError("La revisión del nuevo borrador no es válida. Vuelve a abrir el formulario.")
        solicitud, creada = SolicitudDerecho.objects.get_or_create(
            solicitante=usuario, clave_creacion=datos["clave_creacion"], defaults=contenido,
        )
        if creada:
            EventoSolicitudDerecho.objects.create(solicitud=solicitud, accion="CREADA", revision=solicitud.revision, realizado_por=usuario)
        return solicitud
    solicitud = get_object_or_404(SolicitudDerecho.objects.select_for_update(),
                                 identificador=identificador, solicitante=usuario)
    if solicitud.estado != "BORRADOR":
        raise ValidationError("Esta solicitud ya no se puede editar como borrador.")
    if solicitud.revision != datos["revision"]:
        raise ValidationError("Este borrador cambió en otra pestaña. Recarga para revisar la última versión antes de guardar.")
    if datos["clave_creacion"] != solicitud.clave_creacion:
        raise ValidationError("El formulario no corresponde a este borrador. Vuelve a abrirlo.")
    if any(getattr(solicitud, campo) != valor for campo, valor in contenido.items()):
        for campo, valor in contenido.items():
            setattr(solicitud, campo, valor)
        solicitud.revision += 1
        solicitud.save(update_fields=[*CAMPOS_BORRADOR, "revision", "actualizada_at"])
        EventoSolicitudDerecho.objects.create(solicitud=solicitud, accion="EDITADA", revision=solicitud.revision, realizado_por=usuario)
    return solicitud


@transaction.atomic
def enviar_solicitud(*, usuario, identificador, revision):
    from .canal_privacidad import bloquear_configuracion, canal_disponible
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied
    cfg = bloquear_configuracion()
    solicitud = get_object_or_404(SolicitudDerecho.objects.select_for_update(),
                                 identificador=identificador, solicitante=usuario)
    if solicitud.estado != "BORRADOR":
        return solicitud
    if not canal_disponible(cfg):
        raise ValidationError("La recepción institucional no está habilitada. Tu borrador se conserva sin enviar.")
    if solicitud.revision != revision:
        raise ValidationError("El borrador cambió. Revisa la última versión antes de enviarlo.")
    ahora = timezone.now()
    solicitud.estado = "RECIBIDA"
    solicitud.enviada_at = ahora
    solicitud.fecha_limite = timezone.localdate(ahora) + timedelta(days=30)
    solicitud.recepcion = {"entidad": cfg.entidad, "contacto": cfg.contacto, "revision_configuracion": cfg.revision,
                          "medio_respuesta": "Cuenta personal del sistema, elegido expresamente al enviar"}
    solicitud.revision += 1
    solicitud.save(update_fields=["estado", "enviada_at", "fecha_limite", "recepcion", "revision", "actualizada_at"])
    EventoSolicitudDerecho.objects.create(solicitud=solicitud, accion="ENVIADA", revision=solicitud.revision, realizado_por=usuario)
    return solicitud


@transaction.atomic
def responder_solicitud(*, usuario, identificador, datos):
    from .canal_privacidad import bloquear_configuracion, puede_responder
    cfg = bloquear_configuracion()
    if not puede_responder(usuario, cfg):
        raise PermissionDenied
    solicitud = get_object_or_404(SolicitudDerecho.objects.select_for_update(),
                                 identificador=identificador, estado__in=["RECIBIDA", "RESPONDIDA"])
    if solicitud.solicitante_id == usuario.pk:
        raise PermissionDenied("No puedes responder tu propia solicitud.")
    if solicitud.estado != "RECIBIDA":
        raise ValidationError("Esta solicitud ya tiene una respuesta definitiva.")
    if solicitud.revision != datos["revision"]:
        raise ValidationError("La solicitud cambió. Recarga antes de responder.")
    if not datos.get("identidad_verificada") or not datos.get("confirmar") or not datos.get("verificacion", "").strip() or not datos.get("respuesta", "").strip():
        raise ValidationError("Registra la verificación de identidad y confirma la respuesta.")
    solicitud.estado = "RESPONDIDA"
    solicitud.respuesta = datos["respuesta"]
    solicitud.respondida_por = usuario
    solicitud.respondida_at = timezone.now()
    solicitud.verificacion_identidad = datos["verificacion"]
    solicitud.revision += 1
    solicitud.save(update_fields=["estado", "respuesta", "respondida_por", "respondida_at",
                                  "verificacion_identidad", "revision", "actualizada_at"])
    EventoSolicitudDerecho.objects.create(solicitud=solicitud, accion="RESPONDIDA", revision=solicitud.revision, realizado_por=usuario)
    return solicitud

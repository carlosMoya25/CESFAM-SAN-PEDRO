"""Metadatos de actividad. Nunca recibe formularios, cabeceras ni excepciones."""
import logging
import uuid
from contextlib import contextmanager
from functools import wraps

from django.core.management.base import CommandError
from django.db import transaction

from .models import EventoAuditoria
from .logging import contexto_actual


logger = logging.getLogger("cesfam.auditoria")


@contextmanager
def contexto_auditoria(*, usuario=None, origen="SISTEMA"):
    contexto = {"usuario": usuario, "origen": origen, "solicitud_id": uuid.uuid4()}
    token = contexto_actual.set(contexto)
    try:
        yield contexto
    finally:
        contexto_actual.reset(token)


def registrar_evento(*, modulo, accion, usuario=None, usuario_id=None, **datos):
    contexto = contexto_actual.get() or {}
    usuario = contexto.get("usuario") or usuario
    base = {campo: contexto[campo] for campo in ("origen", "solicitud_id", "ruta", "vista", "metodo") if campo in contexto}
    evento = EventoAuditoria.objects.create(modulo=modulo, accion=accion, usuario_id=usuario.pk if usuario else usuario_id, **(base | datos))
    extra = {campo: getattr(evento, campo) for campo in (
        "solicitud_id", "usuario_id", "origen", "modulo", "accion", "resultado", "modelo", "objeto_id", "estado_http", "duracion_ms", "vista")}
    extra["evento_id"] = evento.pk
    nivel = logging.ERROR if evento.resultado == "FALLIDA" else logging.WARNING if evento.resultado == "RECHAZADA" else logging.INFO
    transaction.on_commit(lambda: logger.log(nivel, "evento_auditoria", extra=extra), robust=True)
    return evento


def intentar_registrar_evento(**datos):
    try:
        # El savepoint evita dejar una transacción externa inutilizable al fallar este registro auxiliar.
        with transaction.atomic():
            return registrar_evento(**datos)
    except Exception:
        logger.warning("auditoria_no_disponible", extra={"accion": "AUDITORIA_NO_DISPONIBLE", "resultado": "FALLIDA"})
        return None


def marcar_formulario(form):
    contexto = contexto_actual.get()
    if contexto is not None and form is not None and form.is_bound and form.errors:
        contexto["rechazada"] = True


def marcar_rechazo():
    contexto = contexto_actual.get()
    if contexto is not None:
        contexto["rechazada"] = True


def auditar_comando(funcion):
    @wraps(funcion)
    def ejecutar(self, *args, **opciones):
        with contexto_auditoria(origen="COMANDO") as contexto:
            intentar_registrar_evento(modulo=self.__module__.split(".")[0], accion="COMANDO_INICIADO", modelo=self.__module__)
            try:
                resultado = funcion(self, *args, **opciones)
            except Exception:
                intentar_registrar_evento(modulo=self.__module__.split(".")[0], accion="COMANDO_FINALIZADO", modelo=self.__module__, resultado="FALLIDA")
                logger.error("comando_fallido", exc_info=True, extra={"accion": "COMANDO_FALLIDO", "resultado": "FALLIDA"})
                raise CommandError(f"El comando no se completó. Revisa los registros con la referencia {contexto['solicitud_id']}.") from None
            intentar_registrar_evento(modulo=self.__module__.split(".")[0], accion="COMANDO_FINALIZADO", modelo=self.__module__)
            return resultado
    return ejecutar

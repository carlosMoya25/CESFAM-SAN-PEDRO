"""Salida JSON con lista permitida; no serializa mensajes ni variables de excepciones."""
import json
import logging
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path


contexto_actual = ContextVar("auditoria", default=None)


class FormatoSeguroJSON(logging.Formatter):
    def format(self, record):
        contexto = contexto_actual.get() or {}
        datos = {"fecha": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                 "nivel": record.levelname, "logger": record.name}
        for campo in ("usuario_id", "origen", "modulo", "accion", "resultado", "modelo", "objeto_id",
                      "evento_id", "estado_http", "duracion_ms", "vista"):
            valor = getattr(record, campo, None)
            if isinstance(valor, (str, int, bool)):
                datos[campo] = valor
        identificador = getattr(record, "solicitud_id", contexto.get("solicitud_id"))
        if identificador:
            try:
                datos["solicitud_id"] = str(uuid.UUID(str(identificador)))
            except (ValueError, AttributeError):
                pass
        if "usuario_id" not in datos and contexto.get("usuario"):
            datos["usuario_id"] = contexto["usuario"].pk
        if record.exc_info and record.exc_info[0]:
            datos["excepcion"] = record.exc_info[0].__name__
            datos["pila"] = [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                             for frame in traceback.extract_tb(record.exc_info[2])[-12:]]
        return json.dumps(datos, ensure_ascii=True)

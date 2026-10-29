import time
import uuid

from django.conf import settings

from .auditoria import contexto_actual, contexto_auditoria, intentar_registrar_evento


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        contexto = contexto_actual.get()
        match = request.resolver_match
        if contexto is not None and match is not None:
            contexto.update(ruta=match.route[:240], vista=match.view_name[:150])

    def __call__(self, request):
        if request.path_info.startswith("/" + settings.STATIC_URL.strip("/") + "/"):
            return self.get_response(request)
        usuario = request.user if request.user.is_authenticated else None
        with contexto_auditoria(usuario=usuario, origen="WEB") as contexto:
            contexto["metodo"] = request.method[:10]
            inicio = time.monotonic()
            response = self.get_response(request)
            if not contexto.get("vista"):
                self.process_view(request, None, None, None)
            resultado = "FALLIDA" if response.status_code >= 500 else "RECHAZADA" if response.status_code >= 400 or contexto.get("rechazada") else "FINALIZADA"
            vista = contexto.get("vista", "")
            modulo = request.resolver_match.app_name if request.resolver_match else ""
            if not modulo:
                modulo = "usuarios" if vista.startswith("account_") or vista in ("login", "logout") else "core"
            identificador = ""
            if request.resolver_match:
                for campo in ("pk", "identificador", "importacion_id"):
                    valor = request.resolver_match.kwargs.get(campo)
                    if isinstance(valor, (int, uuid.UUID)):
                        identificador = str(valor)
                        break
            intentar_registrar_evento(modulo=modulo, accion="CONSULTAR" if request.method in ("GET", "HEAD") else "SOLICITUD_HTTP",
                resultado=resultado, estado_http=response.status_code, objeto_id=identificador,
                duracion_ms=min(round((time.monotonic() - inicio) * 1000), 2147483647))
            response["X-Request-ID"] = str(contexto["solicitud_id"])
            return response

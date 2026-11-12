from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class CambioClaveObligatorioMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        usuario = request.user
        if usuario.is_authenticated and usuario.debe_cambiar_clave:
            permitidas = {"usuarios:cambiar_clave", "logout", "account_logout",
                          "aviso_privacidad", "confirmar_privacidad"}
            permitidas.update({"mis_derechos", "crear_derecho", "detalle_derecho", "editar_derecho", "enviar_derecho"})
            if request.resolver_match.view_name not in permitidas:
                return redirect("usuarios:cambiar_clave")

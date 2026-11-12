from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from core.auditoria import intentar_registrar_evento, marcar_rechazo


Usuario = get_user_model()


class CesfamAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class CesfamSocialAccountAdapter(DefaultSocialAccountAdapter):

    def is_open_for_signup(self, request, sociallogin):
        """
        No permitimos que Google cree usuarios nuevos.
        Los usuarios deben existir previamente en el sistema.
        """
        return False

    def pre_social_login(self, request, sociallogin):
        """
        Vincula el login de Google con un usuario previamente
        autorizado utilizando su correo electrónico.
        """

        # Si la cuenta Google ya está vinculada, continuar.
        if sociallogin.is_existing:
            return

        email = (
            sociallogin.account.extra_data.get("email", "")
            .strip()
            .lower()
        )

        if not email:
            marcar_rechazo()
            intentar_registrar_evento(modulo="usuarios", accion="ACCESO_FALLIDO", resultado="RECHAZADA")
            messages.error(
                request,
                "Google no proporcionó un correo electrónico válido."
            )
            raise ImmediateHttpResponse(
                redirect("login")
            )

        try:
            usuario = Usuario.objects.get(
                email__iexact=email
            )

        except Usuario.DoesNotExist:
            marcar_rechazo()
            intentar_registrar_evento(modulo="usuarios", accion="ACCESO_FALLIDO", resultado="RECHAZADA")

            messages.error(
                request,
                "Tu cuenta de Google no está autorizada para acceder "
                "al sistema. Comunícate con el administrador."
            )

            raise ImmediateHttpResponse(
                redirect("login")
            )

        if not usuario.is_active:
            marcar_rechazo()
            intentar_registrar_evento(modulo="usuarios", accion="ACCESO_FALLIDO", resultado="RECHAZADA")

            messages.error(
                request,
                "Tu cuenta se encuentra deshabilitada. "
                "Comunícate con el administrador."
            )

            raise ImmediateHttpResponse(
                redirect("login")
            )

        # Vincular la cuenta Google al usuario existente.
        with transaction.atomic():
            sociallogin.connect(request, usuario)

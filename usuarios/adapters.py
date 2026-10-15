from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect


Usuario = get_user_model()


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

            messages.error(
                request,
                "Tu cuenta de Google no está autorizada para acceder "
                "al sistema. Comunícate con el administrador."
            )

            raise ImmediateHttpResponse(
                redirect("login")
            )

        if not usuario.is_active:

            messages.error(
                request,
                "Tu cuenta se encuentra deshabilitada. "
                "Comunícate con el administrador."
            )

            raise ImmediateHttpResponse(
                redirect("login")
            )

        # Vincular la cuenta Google al usuario existente.
        sociallogin.connect(
            request,
            usuario
        )
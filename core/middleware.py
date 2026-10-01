from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


class SessionExpiredMiddleware:

    COOKIE_NAME = "cesfam_session_active"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        login_url = reverse("login")

        # Dejamos pasar normalmente la página de login.
        if request.path == login_url:
            response = self.get_response(request)

            # Si acaba de iniciar sesión correctamente,
            # Django ya tendrá un usuario autenticado.
            if request.user.is_authenticated:
                response.set_cookie(
                    self.COOKIE_NAME,
                    "1",
                    max_age=30 * 60,
                    httponly=True,
                    samesite="Lax",
                )

            return response

        # Usuario autenticado: mantenemos actualizada la marca.
        if request.user.is_authenticated:

            response = self.get_response(request)

            response.set_cookie(
                self.COOKIE_NAME,
                "1",
                max_age=30 * 60,
                httponly=True,
                samesite="Lax",
            )

            return response

        # No está autenticado, pero el navegador indica que
        # anteriormente existía una sesión.
        if request.COOKIES.get(self.COOKIE_NAME):

            params = urlencode({
                "expired": "1",
                "next": request.get_full_path(),
            })

            response = redirect(f"{login_url}?{params}")

            response.delete_cookie(self.COOKIE_NAME)

            return response

        return self.get_response(request)
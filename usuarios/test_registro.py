from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .adapters import CesfamSocialAccountAdapter


Usuario = get_user_model()


class RegistroCerradoTests(TestCase):
    def test_registro_publico_no_ofrece_formulario_ni_crea_cuenta(self):
        url = reverse("account_signup")
        anteriores = Usuario.objects.count()
        for metodo in ("get", "post"):
            with self.subTest(metodo=metodo):
                response = getattr(self.client, metodo)(url, {
                    "email": "externo@example.com",
                    "password1": "Temporal-Segura-472!",
                    "password2": "Temporal-Segura-472!",
                })
                self.assertTemplateUsed(response, "account/signup_closed.html")
                self.assertNotContains(response, 'name="password1"')
                self.assertEqual(Usuario.objects.count(), anteriores)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_cuenta_autorizada_conserva_inicio_de_sesion_local(self):
        usuario = Usuario.objects.create_user(email="autorizado@example.com", password="Temporal-Segura-472!")
        response = self.client.post(reverse("login"), {
            "username": usuario.email, "password": "Temporal-Segura-472!",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_google_sigue_vinculando_solo_cuentas_autorizadas(self):
        usuario = Usuario.objects.create_user(email="google-autorizado@example.com")
        request = self.client.get(reverse("login")).wsgi_request
        adapter = CesfamSocialAccountAdapter()
        desconocido = SocialLogin(
            user=Usuario(email="desconocido@example.com"),
            account=SocialAccount(provider="google", uid="desconocido", extra_data={"email": "desconocido@example.com"}),
        )
        self.assertFalse(adapter.is_open_for_signup(request, desconocido))
        with self.assertRaises(ImmediateHttpResponse):
            adapter.pre_social_login(request, desconocido)
        self.assertFalse(Usuario.objects.filter(email="desconocido@example.com").exists())
        autorizado = SocialLogin(
            user=Usuario(email=usuario.email),
            account=SocialAccount(provider="google", uid="autorizado", extra_data={"email": usuario.email}),
        )
        adapter.pre_social_login(request, autorizado)
        self.assertTrue(SocialAccount.objects.filter(provider="google", uid="autorizado", user=usuario).exists())

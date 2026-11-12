from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from . import privacidad
from .models import ConstanciaPrivacidad


class PrivacidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(email="lectura@example.com")
        cls.otro = get_user_model().objects.create_user(email="otra-lectura@example.com")

    def datos(self, **cambios):
        return {"version": privacidad.VERSION, "huella": privacidad.HUELLA, "lectura": "si"} | cambios

    def test_aviso_publico_no_registra_lectura_y_ofrece_inicio_sesion(self):
        self.client.cookies["cesfam_session_active"] = "1"
        response = self.client.get(reverse("aviso_privacidad"))
        self.assertContains(response, privacidad.TITULO)
        self.assertContains(response, "Iniciar sesión")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(ConstanciaPrivacidad.objects.count(), 0)

    def test_login_ofrece_enlace_publico(self):
        self.assertContains(self.client.get(reverse("login")), reverse("aviso_privacidad"))

    def test_cualquier_usuario_sin_rol_puede_consultar_sin_confirmar(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("aviso_privacidad"))
        self.assertContains(response, "Confirmar lectura")
        self.assertContains(response, "Puedes seguir utilizando el sistema sin confirmar")
        self.assertContains(response, 'name="lectura" value="si" required')
        self.assertNotContains(response, "checked")
        self.assertContains(self.client.get(reverse("dashboard")), "Ley 21.719 · Privacidad")
        self.assertEqual(ConstanciaPrivacidad.objects.count(), 0)

    def test_confirmacion_autenticada_guarda_copia_y_no_duplica_ni_cambia_fecha(self):
        self.client.force_login(self.usuario)
        url = reverse("confirmar_privacidad")
        self.assertRedirects(self.client.post(url, self.datos()), reverse("aviso_privacidad"))
        constancia = ConstanciaPrivacidad.objects.get()
        self.assertEqual(constancia.usuario, self.usuario)
        self.assertEqual(constancia.texto, privacidad.TEXTO)
        self.assertEqual(constancia.declaracion, privacidad.DECLARACION)
        self.assertEqual(constancia.huella, privacidad.HUELLA)
        fecha = constancia.fecha
        self.client.post(url, self.datos())
        self.assertEqual(ConstanciaPrivacidad.objects.count(), 1)
        constancia.refresh_from_db()
        self.assertEqual(fecha, constancia.fecha)
        self.assertContains(self.client.get(reverse("aviso_privacidad")), "Lectura confirmada")

    def test_rechaza_confirmacion_sin_casilla_o_de_otra_version(self):
        self.client.force_login(self.usuario)
        for cambios in ({"lectura": ""}, {"version": "anterior"}, {"huella": "otra"}):
            response = self.client.post(reverse("confirmar_privacidad"), self.datos(**cambios))
            self.assertEqual(response.status_code, 400)
        self.assertEqual(ConstanciaPrivacidad.objects.count(), 0)

    def test_no_admite_confirmacion_anonima_get_ni_sin_csrf(self):
        url = reverse("confirmar_privacidad")
        self.assertEqual(self.client.post(url, self.datos()).status_code, 302)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(url).status_code, 405)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(url, self.datos()).status_code, 403)
        self.assertFalse(ConstanciaPrivacidad.objects.exists())

    def test_no_puede_registrar_por_otro_usuario_ni_ver_su_constancia(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("confirmar_privacidad"), self.datos(usuario=self.otro.pk))
        self.assertEqual(ConstanciaPrivacidad.objects.get().usuario, self.usuario)
        self.client.force_login(self.otro)
        self.assertNotContains(self.client.get(reverse("aviso_privacidad")), "Lectura confirmada")

    def test_usuario_con_cambio_clave_pendiente_puede_leer_y_confirmar(self):
        self.usuario.debe_cambiar_clave = True
        self.usuario.save(update_fields=["debe_cambiar_clave"])
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("aviso_privacidad")).status_code, 200)
        self.client.post(reverse("confirmar_privacidad"), self.datos())
        self.assertTrue(ConstanciaPrivacidad.objects.filter(usuario=self.usuario).exists())
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("usuarios:cambiar_clave"), fetch_redirect_response=False)


class ConsultaConstanciasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.funcionario = Usuario.objects.create_user(email="funcionario-consulta@example.com")
        cls.staff = Usuario.objects.create_user(email="staff-consulta@example.com", is_staff=True)
        cls.admin = Usuario.objects.create_user(email="admin-consulta@example.com")
        cls.tecnico = Usuario.objects.create_user(email="tecnico-consulta@example.com")
        cls.superusuario = Usuario.objects.create_superuser(email="super-consulta@example.com")
        cls.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        cls.tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        cls.inactivo = Usuario.objects.create_user(
            email="autor-historico@example.com", nombres="Autor", apellido_paterno="Histórico", is_active=False,
        )
        cls.registro = ConstanciaPrivacidad.objects.create(
            usuario=cls.inactivo, version=privacidad.VERSION, huella=privacidad.HUELLA,
            texto=privacidad.TEXTO, declaracion=privacidad.DECLARACION,
        )

    def test_administrador_tecnico_y_superusuario_ven_constancias_en_la_misma_pagina(self):
        for usuario in (self.admin, self.tecnico, self.superusuario):
            with self.subTest(usuario=usuario.email):
                self.client.force_login(usuario)
                response = self.client.get(reverse("aviso_privacidad"))
                self.assertContains(response, 'href="#constancias-usuarios"')
                self.assertContains(response, "Constancias de lectura de usuarios")
                self.assertContains(response, self.inactivo.email)
                self.assertContains(response, "cuenta inactiva")
                self.assertContains(response, "Aviso actual")
                self.assertIn("no-store", response["Cache-Control"])

    def test_anonimo_funcionario_y_staff_no_reciben_datos_aunque_fuercen_parametros(self):
        for usuario in (None, self.funcionario, self.staff):
            with self.subTest(usuario=usuario):
                if usuario:
                    self.client.force_login(usuario)
                else:
                    self.client.logout()
                response = self.client.get(reverse("aviso_privacidad"), {
                    "pagina_constancias": "1", "puede_ver_constancias": "true",
                })
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Constancias de lectura de usuarios")
                self.assertNotContains(response, self.inactivo.email)
                self.assertFalse(response.context["puede_ver_constancias"])
                self.assertIsNone(response.context["constancias"])

    def test_paginacion_incluye_versiones_anteriores_y_admite_pagina_invalida(self):
        ConstanciaPrivacidad.objects.bulk_create([
            ConstanciaPrivacidad(usuario=self.inactivo, version=f"anterior-{i}", huella="a" * 64,
                                texto="Aviso anterior", declaracion="Lectura anterior")
            for i in range(21)
        ])
        self.client.force_login(self.tecnico)
        response = self.client.get(reverse("aviso_privacidad"))
        self.assertEqual(len(response.context["constancias"]), 20)
        self.assertContains(response, "Aviso anterior")
        self.assertContains(response, "Siguiente")
        response = self.client.get(reverse("aviso_privacidad"), {"pagina_constancias": 2})
        self.assertEqual(len(response.context["constancias"]), 2)
        self.assertContains(response, "Anterior")
        for pagina in ("invalida", "999999", "-1"):
            self.assertEqual(self.client.get(reverse("aviso_privacidad"), {"pagina_constancias": pagina}).status_code, 200)

    def test_apartado_muestra_estado_vacio(self):
        ConstanciaPrivacidad.objects.all().delete()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("aviso_privacidad")), "Todavía no hay constancias")

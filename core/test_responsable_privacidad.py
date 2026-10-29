from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from usuarios.desvinculacion import desactivar_usuario
from .models import ConfiguracionPrivacidad, HistorialResponsablePrivacidad
from .privacidad_services import asignar_responsable


class ResponsablePrivacidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_user(email="admin-responsable@example.com")
        cls.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        cls.tecnico = Usuario.objects.create_user(email="tecnico-responsable@example.com")
        cls.tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        cls.usuario = Usuario.objects.create_user(email="persona-responsable@example.com")
        cls.inactivo = Usuario.objects.create_user(email="inactivo-responsable@example.com", is_active=False)

    def datos(self, **cambios):
        return {"responsable": self.usuario.pk, "motivo": "Asignación institucional", "revision": 0} | cambios

    def test_administrador_asigna_y_cambia_con_historial(self):
        self.client.force_login(self.admin)
        url = reverse("cambiar_responsable_privacidad")
        self.assertContains(self.client.get(reverse("aviso_privacidad")), "Guardar responsable")
        response = self.client.post(url, self.datos())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConfiguracionPrivacidad.objects.get(pk=1).responsable, self.usuario)
        cambio = HistorialResponsablePrivacidad.objects.get()
        self.assertIsNone(cambio.anterior)
        self.assertEqual(cambio.administrador, self.admin)
        self.client.post(url, self.datos(responsable=self.tecnico.pk, revision=1))
        self.assertEqual(ConfiguracionPrivacidad.objects.get(pk=1).responsable, self.tecnico)
        cambio = HistorialResponsablePrivacidad.objects.first()
        self.assertEqual(cambio.anterior, self.usuario)
        self.assertEqual(cambio.nuevo, self.tecnico)
        self.assertEqual(HistorialResponsablePrivacidad.objects.count(), 2)

    def test_tecnico_y_funcionario_solo_ven_actual_sin_formulario_ni_historial(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cambiar_responsable_privacidad"), self.datos(motivo="Motivo reservado de prueba"))
        for usuario in (self.usuario, self.tecnico):
            self.client.force_login(usuario)
            response = self.client.get(reverse("aviso_privacidad"))
            self.assertContains(response, self.usuario.email)
            self.assertNotContains(response, "Guardar responsable")
            self.assertNotContains(response, "Motivo reservado de prueba")
            self.assertEqual(self.client.post(reverse("cambiar_responsable_privacidad"), self.datos()).status_code, 403)
            self.assertIsNone(response.context["historial_responsable"])

    def test_publico_no_recibe_asignacion_ni_datos_internos(self):
        asignar_responsable(administrador=self.admin, responsable_id=self.usuario.pk, motivo="Asignación", revision=0)
        response = self.client.get(reverse("aviso_privacidad"))
        self.assertNotContains(response, self.usuario.email)
        self.assertIsNone(response.context["configuracion_privacidad"])
        self.assertEqual(self.client.post(reverse("cambiar_responsable_privacidad"), self.datos()).status_code, 302)

    def test_rechaza_inactivos_falta_motivo_y_revision_obsoleta(self):
        self.client.force_login(self.admin)
        url = reverse("cambiar_responsable_privacidad")
        for cambios in ({"responsable": self.inactivo.pk}, {"motivo": ""}, {"revision": 8}):
            self.assertEqual(self.client.post(url, self.datos(**cambios)).status_code, 400)
        self.assertFalse(HistorialResponsablePrivacidad.objects.exists())
        self.client.post(url, self.datos())
        self.assertEqual(self.client.post(url, self.datos(responsable=self.tecnico.pk)).status_code, 400)
        self.assertEqual(self.client.post(url, self.datos(revision=1)).status_code, 400)
        self.assertEqual(HistorialResponsablePrivacidad.objects.count(), 1)

    def test_get_no_modifica_y_csrf_es_obligatorio(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("cambiar_responsable_privacidad")).status_code, 405)
        self.client.get(reverse("aviso_privacidad"))
        self.assertFalse(ConfiguracionPrivacidad.objects.exists())
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(reverse("cambiar_responsable_privacidad"), self.datos()).status_code, 403)

    def test_debe_cambiar_responsable_antes_de_desactivarlo(self):
        asignar_responsable(administrador=self.admin, responsable_id=self.usuario.pk, motivo="Asignación", revision=0)
        with self.assertRaisesMessage(ValidationError, "Antes de desactivar"):
            desactivar_usuario(administrador=self.admin, usuario_id=self.usuario.pk, motivo="Baja")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        asignar_responsable(administrador=self.admin, responsable_id=self.tecnico.pk, motivo="Reemplazo", revision=1)
        desactivar_usuario(administrador=self.admin, usuario_id=self.usuario.pk, motivo="Baja")
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

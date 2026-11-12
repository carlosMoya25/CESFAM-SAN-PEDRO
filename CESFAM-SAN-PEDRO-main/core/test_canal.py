from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.desvinculacion import desactivar_usuario
from .canal_privacidad import guardar_configuracion, validar_contacto, cambiar_habilitacion
from .derechos_services import enviar_solicitud, responder_solicitud
from .models import ConfiguracionPrivacidad, HistorialCanalPrivacidad, SolicitudDerecho


class CanalInstitucionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_user(email="admin-canal@example.com")
        cls.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        cls.validador = Usuario.objects.create_user(email="validador-canal@example.com")
        cls.respondedor = Usuario.objects.create_user(email="atencion-canal@example.com")
        cls.coordinador = Usuario.objects.create_user(email="coordinacion-canal@example.com")
        cls.usuario = Usuario.objects.create_user(email="solicitante-canal@example.com", telefono="111")
        cls.otro = Usuario.objects.create_user(email="otra-atencion@example.com")
        cls.tecnico = Usuario.objects.create_user(email="tecnico-canal@example.com")
        cls.tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        cls.cfg = ConfiguracionPrivacidad.objects.create(pk=1, responsable=cls.coordinador)

    def datos_config(self, revision=0, autorizados=None):
        return {"entidad": "Entidad institucional de prueba", "contacto": "contacto@example.com",
                "validador": self.validador, "autorizados": autorizados or [self.respondedor], "revision": revision}

    def habilitar(self):
        guardar_configuracion(usuario=self.admin, datos=self.datos_config())
        validar_contacto(usuario=self.validador, revision=1, evidencia="Atención comprobada por procedimiento institucional")
        cambiar_habilitacion(usuario=self.admin, revision=2, habilitar=True)

    def borrador(self, usuario=None):
        return SolicitudDerecho.objects.create(solicitante=usuario or self.usuario, tipo="RECTIFICACION",
            detalle="Corrijo mi teléfono", campo_rectificar="Teléfono", valor_solicitado="222")

    def enviada(self, usuario=None):
        solicitud = self.borrador(usuario)
        return enviar_solicitud(usuario=usuario or self.usuario, identificador=solicitud.identificador, revision=1)

    def respuesta(self, revision):
        return {"revision": revision, "identidad_verificada": True, "verificacion": "Procedimiento institucional realizado",
                "respuesta": "Se revisó su petición y se informa el resultado.", "confirmar": True}

    def test_nadie_habilita_sin_configuracion_y_validacion(self):
        with self.assertRaises(ValidationError):
            cambiar_habilitacion(usuario=self.admin, revision=0, habilitar=True)
        guardar_configuracion(usuario=self.admin, datos=self.datos_config())
        with self.assertRaises(PermissionDenied):
            validar_contacto(usuario=self.admin, revision=1, evidencia="No es la persona designada")
        with self.assertRaises(ValidationError):
            cambiar_habilitacion(usuario=self.admin, revision=1, habilitar=True)
        self.cfg.refresh_from_db()
        self.assertFalse(self.cfg.canal_habilitado)

    def test_cadena_de_configuracion_validacion_habilitacion_auditada(self):
        self.habilitar()
        self.cfg.refresh_from_db()
        self.assertTrue(self.cfg.canal_habilitado)
        self.assertEqual(self.cfg.contacto_validado_por, self.validador)
        self.assertEqual(self.cfg.revision, 3)
        self.assertEqual(HistorialCanalPrivacidad.objects.count(), 3)
        for usuario in (self.validador, self.respondedor, self.usuario):
            with self.assertRaises(PermissionDenied):
                cambiar_habilitacion(usuario=usuario, revision=3, habilitar=False)

    def test_solo_admin_configura_y_solo_validador_designado_valida(self):
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("panel_institucional")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("panel_institucional")), "Guardar configuración")
        guardar_configuracion(usuario=self.admin, datos=self.datos_config())
        self.client.force_login(self.validador)
        response = self.client.get(reverse("panel_institucional"))
        self.assertContains(response, "Registrar validación")
        self.assertNotContains(response, "Guardar configuración")
        self.assertEqual(self.client.post(reverse("panel_institucional"), {"accion": "habilitar"}).status_code, 403)

    def test_cambiar_configuracion_suspendey_exige_validacion_nueva(self):
        self.habilitar()
        guardar_configuracion(usuario=self.admin, datos=self.datos_config(revision=3, autorizados=[self.otro]))
        self.cfg.refresh_from_db()
        self.assertFalse(self.cfg.canal_habilitado)
        self.assertIsNone(self.cfg.contacto_validado_at)
        with self.assertRaises(ValidationError):
            cambiar_habilitacion(usuario=self.admin, revision=4, habilitar=True)
        with self.assertRaises(ValidationError):
            guardar_configuracion(usuario=self.admin, datos=self.datos_config(revision=3))
        self.assertEqual(HistorialCanalPrivacidad.objects.count(), 4)

    def test_habilitar_no_convierte_borradores_y_enviar_genera_acuse_una_vez(self):
        solicitud = self.borrador()
        self.habilitar()
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "BORRADOR")
        self.client.force_login(self.usuario)
        url = reverse("enviar_derecho", args=[solicitud.identificador])
        self.client.post(url, {"revision": 1, "confirmar": "on"})
        self.client.post(url, {"revision": 1, "confirmar": "on"})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "RECIBIDA")
        self.assertEqual(solicitud.fecha_limite, timezone.localdate() + timedelta(days=30))
        self.assertEqual(solicitud.historial.filter(accion="ENVIADA").count(), 1)
        self.assertTrue(solicitud.folio.startswith("PRIV-R-"))
        self.assertEqual(solicitud.recepcion["contacto"], "contacto@example.com")
        self.assertContains(self.client.get(reverse("detalle_derecho", args=[solicitud.identificador])), "Acuse de recepción")
        self.assertEqual(self.client.get(reverse("editar_derecho", args=[solicitud.identificador])).status_code, 404)

    def test_sin_canal_o_revision_vigente_o_confirmacion_no_envia(self):
        solicitud = self.borrador()
        with self.assertRaises(ValidationError):
            enviar_solicitud(usuario=self.usuario, identificador=solicitud.identificador, revision=1)
        self.habilitar()
        with self.assertRaises(ValidationError):
            enviar_solicitud(usuario=self.usuario, identificador=solicitud.identificador, revision=8)
        self.client.force_login(self.usuario)
        self.client.post(reverse("enviar_derecho", args=[solicitud.identificador]), {"revision": 1})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "BORRADOR")

    def test_solo_autorizados_ven_recibidas_y_nadie_ve_borradores_ajenos(self):
        self.habilitar()
        enviada = self.enviada()
        borrador = self.borrador()
        for usuario in (self.admin, self.tecnico, self.validador):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("bandeja_derechos")).status_code, 403)
            self.assertEqual(self.client.get(reverse("gestionar_derecho", args=[enviada.identificador])).status_code, 403)
        self.client.force_login(self.respondedor)
        self.assertContains(self.client.get(reverse("bandeja_derechos")), enviada.folio)
        self.assertNotContains(self.client.get(reverse("bandeja_derechos")), borrador.folio)
        self.assertEqual(self.client.get(reverse("gestionar_derecho", args=[borrador.identificador])).status_code, 404)
        self.assertEqual(self.client.get(reverse("detalle_derecho", args=[enviada.identificador])).status_code, 404)

    def test_responder_verifica_identidad_y_es_definitivo_sin_cambiar_perfil(self):
        self.habilitar()
        solicitud = self.enviada()
        datos = self.respuesta(solicitud.revision)
        with self.assertRaises(ValidationError):
            responder_solicitud(usuario=self.respondedor, identificador=solicitud.identificador,
                                datos=datos | {"identidad_verificada": False})
        responder_solicitud(usuario=self.respondedor, identificador=solicitud.identificador, datos=datos)
        with self.assertRaises(ValidationError):
            responder_solicitud(usuario=self.respondedor, identificador=solicitud.identificador, datos=datos)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "RESPONDIDA")
        self.assertEqual(solicitud.respondida_por, self.respondedor)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, "111")
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("detalle_derecho", args=[solicitud.identificador]))
        self.assertContains(response, datos["respuesta"])
        self.assertNotContains(response, datos["verificacion"])

    def test_suspender_canal_no_impide_responder_y_retirar_autorizacion_si(self):
        self.habilitar()
        solicitud = self.enviada()
        cambiar_habilitacion(usuario=self.admin, revision=3, habilitar=False)
        self.client.force_login(self.respondedor)
        self.assertEqual(self.client.get(reverse("gestionar_derecho", args=[solicitud.identificador])).status_code, 200)
        guardar_configuracion(usuario=self.admin, datos=self.datos_config(revision=4, autorizados=[self.otro]))
        self.assertEqual(self.client.get(reverse("bandeja_derechos")).status_code, 403)
        self.client.force_login(self.otro)
        self.assertContains(self.client.get(reverse("bandeja_derechos")), solicitud.folio)

    def test_no_puede_responderse_a_si_mismo_ni_enviar_por_otro(self):
        self.habilitar()
        solicitud = self.enviada(self.respondedor)
        with self.assertRaises(PermissionDenied):
            responder_solicitud(usuario=self.respondedor, identificador=solicitud.identificador,
                                datos=self.respuesta(solicitud.revision))
        self.client.force_login(self.otro)
        self.assertEqual(self.client.post(reverse("enviar_derecho", args=[solicitud.identificador]),
                                         {"revision": 1, "confirmar": "on"}).status_code, 404)

    def test_reemplazar_designaciones_antes_de_desactivar(self):
        self.habilitar()
        for usuario in (self.validador, self.respondedor):
            with self.assertRaises(ValidationError):
                desactivar_usuario(administrador=self.admin, usuario_id=usuario.pk, motivo="Cambio institucional")

    def test_csrf_configuracion_envio_y_respuesta(self):
        self.habilitar()
        solicitud = self.enviada()
        cliente = Client(enforce_csrf_checks=True)
        for usuario, url in ((self.admin, reverse("panel_institucional")),
                             (self.usuario, reverse("enviar_derecho", args=[solicitud.identificador])),
                             (self.respondedor, reverse("gestionar_derecho", args=[solicitud.identificador]))):
            cliente.force_login(usuario)
            self.assertEqual(cliente.post(url, {}).status_code, 403)

    def test_formularios_validan_requeridos_y_rutas_funcionan(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("panel_institucional"), {"accion": "configurar"})
        self.assertTrue(response.context["form_configuracion"].errors)
        self.habilitar()
        solicitud = self.enviada()
        self.client.force_login(self.respondedor)
        response = self.client.post(reverse("gestionar_derecho", args=[solicitud.identificador]), {})
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.client.post(reverse("gestionar_derecho", args=[solicitud.identificador]),
                                         self.respuesta(solicitud.revision)).status_code, 302)
        self.assertContains(self.client.get(reverse("gestionar_derecho", args=[solicitud.identificador])), "Respuesta publicada")

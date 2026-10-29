import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import EventoSolicitudDerecho, SolicitudDerecho


class DerechosUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(email="derechos@example.com", telefono="12345")
        cls.otro = get_user_model().objects.create_user(email="otro-derechos@example.com")
        cls.admin = get_user_model().objects.create_superuser(email="admin-derechos@example.com")

    def setUp(self):
        self.client.force_login(self.usuario)

    def datos(self, **cambios):
        return {"tipo": "ACCESO", "detalle": "Deseo consultar los datos de mi cuenta y mis solicitudes.",
                "campo_rectificar": "", "valor_solicitado": "", "revision": 0,
                "clave_creacion": str(uuid.uuid4())} | cambios

    def crear(self, **cambios):
        response = self.client.post(reverse("crear_derecho"), self.datos(**cambios))
        self.assertEqual(response.status_code, 302)
        return SolicitudDerecho.objects.latest("pk")

    def test_crea_borrador_sin_constancia_y_registra_folio_e_historial(self):
        solicitud = self.crear()
        self.assertEqual(solicitud.solicitante, self.usuario)
        self.assertEqual(solicitud.estado, "BORRADOR")
        self.assertTrue(solicitud.folio.startswith("PRIV-B-"))
        evento = solicitud.historial.get()
        self.assertEqual((evento.accion, evento.revision), ("CREADA", 1))
        response = self.client.get(reverse("detalle_derecho", args=[solicitud.identificador]))
        self.assertContains(response, solicitud.folio)
        self.assertContains(response, "no acredita recepción institucional")
        self.assertContains(response, "Borrador creado")
        self.assertIn("no-store", response["Cache-Control"])

    def test_doble_envio_no_duplica_ni_modifica_borrador_previo(self):
        datos = self.datos()
        primero = self.client.post(reverse("crear_derecho"), datos)
        segundo = self.client.post(reverse("crear_derecho"), datos | {"detalle": "Contenido repetido cambiado"})
        self.assertEqual(primero.url, segundo.url)
        self.assertEqual(SolicitudDerecho.objects.count(), 1)
        self.assertEqual(EventoSolicitudDerecho.objects.count(), 1)
        self.assertEqual(SolicitudDerecho.objects.get().detalle, datos["detalle"])

    def test_rectificacion_valida_no_modifica_cuenta(self):
        solicitud = self.crear(tipo="RECTIFICACION", detalle="Actualizar mi teléfono de contacto.",
                               campo_rectificar="Teléfono", valor_solicitado="98765")
        self.assertEqual(solicitud.valor_solicitado, "98765")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, "12345")
        self.assertContains(self.client.get(reverse("detalle_derecho", args=[solicitud.identificador])), "98765")

    def test_valida_campos_y_no_admite_otros_derechos_ni_textos_excesivos(self):
        for cambios in ({"tipo": "RECTIFICACION"}, {"detalle": ""}, {"detalle": "x" * 2001},
                        {"tipo": "SUPRESION"}, {"clave_creacion": "invalida"}, {"revision": 8}):
            response = self.client.post(reverse("crear_derecho"), self.datos(**cambios))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(SolicitudDerecho.objects.exists())

    def test_solicitante_estado_y_revision_no_se_toman_de_campos_inyectados(self):
        solicitud = self.crear(solicitante=self.otro.pk, estado="RESPONDIDA", responsable=self.admin.pk)
        self.assertEqual(solicitud.solicitante, self.usuario)
        self.assertEqual(solicitud.estado, "BORRADOR")
        self.assertEqual(solicitud.revision, 1)

    def test_otro_usuario_y_administrador_no_ven_ni_editan_borradores_ajenos(self):
        solicitud = self.crear(detalle="Contenido privado para pruebas de autorización.")
        for usuario in (self.otro, self.admin):
            self.client.force_login(usuario)
            self.assertNotContains(self.client.get(reverse("mis_derechos")), solicitud.folio)
            for ruta in ("detalle_derecho", "editar_derecho"):
                self.assertEqual(self.client.get(reverse(ruta, args=[solicitud.identificador])).status_code, 404)
            self.assertEqual(self.client.post(reverse("editar_derecho", args=[solicitud.identificador]),
                                             self.datos()).status_code, 404)

    def test_edita_con_historial_y_rechaza_pestana_desactualizada(self):
        solicitud = self.crear()
        url = reverse("editar_derecho", args=[solicitud.identificador])
        datos = self.datos(clave_creacion=str(solicitud.clave_creacion), revision=1, detalle="Alcance actualizado")
        response = self.client.get(url)
        self.assertEqual(response.context["form"].initial["revision"], 1)
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(self.client.post(url, datos | {"detalle": "Versión obsoleta"}).status_code, 200)
        solicitud.refresh_from_db()
        self.assertEqual((solicitud.revision, solicitud.detalle), (2, "Alcance actualizado"))
        self.assertEqual(solicitud.historial.count(), 2)
        # Guardar sin cambios no añade eventos redundantes.
        self.client.post(url, datos | {"revision": 2})
        self.assertEqual(solicitud.historial.count(), 2)

    def test_cambiar_rectificacion_a_acceso_limpia_campos_anteriores(self):
        solicitud = self.crear(tipo="RECTIFICACION", campo_rectificar="Teléfono", valor_solicitado="98765")
        self.client.post(reverse("editar_derecho", args=[solicitud.identificador]),
                         self.datos(clave_creacion=str(solicitud.clave_creacion), revision=1,
                                    campo_rectificar="Teléfono", valor_solicitado="98765"))
        solicitud.refresh_from_db()
        self.assertEqual((solicitud.campo_rectificar, solicitud.valor_solicitado), ("", ""))

    def test_no_admite_cambiar_clave_de_otro_formulario(self):
        solicitud = self.crear()
        response = self.client.post(reverse("editar_derecho", args=[solicitud.identificador]), self.datos(revision=1))
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(solicitud.historial.count(), 1)

    def test_anonimos_y_csrf_y_metodos(self):
        solicitud = self.crear()
        cliente = Client()
        for ruta in (reverse("mis_derechos"), reverse("crear_derecho"), reverse("detalle_derecho", args=[solicitud.identificador])):
            self.assertEqual(cliente.get(ruta).status_code, 302)
        self.assertEqual(self.client.post(reverse("mis_derechos")).status_code, 405)
        self.assertEqual(self.client.post(reverse("detalle_derecho", args=[solicitud.identificador])).status_code, 405)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(reverse("crear_derecho"), self.datos()).status_code, 403)
        self.assertEqual(cliente.post(reverse("editar_derecho", args=[solicitud.identificador]), self.datos()).status_code, 403)

    def test_paginas_invalidas_y_contenido_escapado(self):
        solicitud = self.crear(detalle='<script>alert("No ejecutar")</script>')
        response = self.client.get(reverse("detalle_derecho", args=[solicitud.identificador]))
        self.assertNotContains(response, '<script>alert(')
        self.assertContains(response, "&lt;script&gt;")
        for pagina in ("invalida", "-1", "99999"):
            self.assertEqual(self.client.get(reverse("mis_derechos"), {"pagina": pagina}).status_code, 200)

    def test_acceso_a_privacidad_disponible_con_cambio_clave_pendiente(self):
        self.usuario.debe_cambiar_clave = True
        self.usuario.save(update_fields=["debe_cambiar_clave"])
        self.assertEqual(self.client.get(reverse("mis_derechos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("crear_derecho")).status_code, 200)
        self.crear()

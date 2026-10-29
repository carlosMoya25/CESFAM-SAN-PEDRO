from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from organizacion.models import Anexo
from requerimientos.models import EstadoRequerimiento, HistorialRequerimiento, Prioridad, Requerimiento, TipoRequerimiento
from .desvinculacion import desactivar_usuario
from .models import HistorialAdministracion


class DesvinculacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_user(email="admin-baja@example.com")
        cls.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        cls.tecnico = Usuario.objects.create_user(email="tecnico-baja@example.com")
        cls.reemplazo = Usuario.objects.create_user(email="reemplazo-baja@example.com")
        rol = Group.objects.get_or_create(name="Técnico TI")[0]
        cls.tecnico.groups.add(rol)
        cls.reemplazo.groups.add(rol)
        cls.funcionario = Usuario.objects.create_user(email="solicitante-baja@example.com")
        cls.inactivo = Usuario.objects.create_user(email="inactivo-baja@example.com", is_active=False)
        cls.inactivo.groups.add(rol)
        cls.anexo = Anexo.objects.create(nombre="Anexo pruebas de baja")
        cls.abiertas = []
        for estado in ("Asignado", "En proceso", "Resuelto", "Cerrado", "Cancelado", "Pendiente"):
            req = Requerimiento.objects.create(
                titulo=f"Confidencial-{estado}", descripcion="Descripción privada del solicitante",
                solicitante=cls.funcionario, responsable=cls.tecnico if estado != "Pendiente" else None,
                anexo=cls.anexo, estado=EstadoRequerimiento.objects.get(nombre=estado),
                prioridad=Prioridad.objects.first(), tipo_requerimiento=TipoRequerimiento.objects.first(),
                solucion="Solución histórica" if estado in ("Resuelto", "Cerrado") else "",
            )
            if estado in ("Asignado", "En proceso", "Resuelto"):
                cls.abiertas.append(req)
            elif estado == "Pendiente":
                cls.pendiente = req
            else:
                cls.cerrado = req
        cls.autoria = HistorialRequerimiento.objects.create(
            requerimiento=cls.abiertas[0], usuario=cls.tecnico, accion="Atención original")

    def datos(self, **cambios):
        return {"reemplazo": self.reemplazo.pk, "motivo": "Cambio de dotación", "confirmar": "on"} | cambios

    def baja(self, **cambios):
        return desactivar_usuario(administrador=self.admin, usuario_id=self.tecnico.pk,
                                  reemplazo_id=cambios.get("reemplazo_id", self.reemplazo.pk), motivo="Cambio de dotación")

    def test_baja_reasigna_abiertas_sin_cambiar_estado_solucion_ni_autoria(self):
        originales = [(r.pk, r.estado_id, r.solucion) for r in self.abiertas]
        self.assertEqual(self.baja(), 3)
        self.tecnico.refresh_from_db()
        self.assertFalse(self.tecnico.is_active)
        self.assertEqual(self.tecnico.revision_acceso, 1)
        for pk, estado, solucion in originales:
            req = Requerimiento.objects.get(pk=pk)
            self.assertEqual(req.responsable, self.reemplazo)
            self.assertEqual((req.estado_id, req.solucion, req.solicitante_id), (estado, solucion, self.funcionario.pk))
        self.cerrado.refresh_from_db()
        self.assertEqual(self.cerrado.responsable, self.tecnico)
        self.autoria.refresh_from_db()
        self.assertEqual(self.autoria.usuario, self.tecnico)
        self.assertEqual(HistorialRequerimiento.objects.filter(accion="Reasignación por desactivación de cuenta").count(), 3)
        self.assertEqual(HistorialAdministracion.objects.filter(accion="DESACTIVAR_USUARIO").count(), 1)

    def test_baja_revoca_todas_las_sesiones_incluso_despues_de_reactivar(self):
        clientes = [Client(), Client()]
        for cliente in clientes:
            cliente.force_login(self.tecnico)
        self.baja()
        # Reactivar antes de que los navegadores vuelvan a pedir una página.
        self.client.force_login(self.admin)
        self.client.post(reverse("usuarios:cambiar_estado_usuario", args=[self.tecnico.pk]))
        for cliente in clientes:
            response = cliente.get(reverse("panel_tecnico"))
            self.assertEqual(response.status_code, 302)
            self.assertNotIn("_auth_user_id", cliente.session)
        nuevo = Client()
        self.tecnico.refresh_from_db()
        nuevo.force_login(self.tecnico)
        self.assertEqual(nuevo.get(reverse("panel_tecnico")).status_code, 200)

    def test_reemplazo_invalido_no_realiza_cambios_parciales(self):
        for destino in (None, self.tecnico.pk, self.funcionario.pk, self.inactivo.pk, 999999):
            with self.subTest(destino=destino), self.assertRaises(ValidationError):
                self.baja(reemplazo_id=destino)
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.is_active)
        self.assertFalse(HistorialAdministracion.objects.exists())
        self.assertEqual(Requerimiento.objects.filter(responsable=self.reemplazo).count(), 0)

    def test_no_se_puede_desactivar_dos_veces(self):
        self.baja()
        with self.assertRaises(ValidationError):
            self.baja()
        self.assertEqual(HistorialAdministracion.objects.filter(accion="DESACTIVAR_USUARIO").count(), 1)

    def test_sin_pendientes_permite_baja_sin_reemplazo(self):
        self.assertEqual(desactivar_usuario(administrador=self.admin, usuario_id=self.funcionario.pk,
                                           motivo="Cambio de dotación"), 0)

    def test_pantalla_get_solo_revisa_y_post_requiere_confirmacion_y_csrf(self):
        self.client.force_login(self.admin)
        url = reverse("usuarios:desvincular_usuario", args=[self.tecnico.pk])
        self.assertContains(self.client.get(url), "Solicitudes que requieren continuidad (3)")
        self.client.post(url, self.datos(confirmar=""))
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.is_active)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(url, self.datos()).status_code, 403)
        self.assertRedirects(self.client.post(url, self.datos()), reverse("usuarios:detalle_usuario", args=[self.tecnico.pk]))

    def test_otro_rol_no_puede_desactivar_ni_forzar_reasignacion(self):
        for usuario in (self.tecnico, self.funcionario):
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(reverse("usuarios:desvincular_usuario", args=[self.reemplazo.pk]), self.datos()).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("usuarios:desvincular_usuario", args=[self.admin.pk]), self.datos())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_edicion_no_permite_saltar_desvinculacion_ni_retirar_rol_con_pendientes(self):
        from .forms import UsuarioAdminForm
        datos = {"email": self.tecnico.email, "nombres": "Tecnico", "apellido_paterno": "Prueba",
                 "roles": list(self.tecnico.groups.values_list("pk", flat=True)), "is_active": ""}
        form = UsuarioAdminForm(datos, instance=self.tecnico, administrador=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn("is_active", form.errors)
        rol = Group.objects.get_or_create(name="Funcionario")[0]
        form = UsuarioAdminForm(datos | {"is_active": "on", "roles": [rol.pk]},
                                instance=get_user_model().objects.get(pk=self.tecnico.pk), administrador=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn("roles", form.errors)

    def test_panel_y_urls_restringen_detalle_a_responsable_o_administrador(self):
        self.client.force_login(self.reemplazo)
        response = self.client.get(reverse("panel_tecnico"))
        self.assertNotContains(response, "Confidencial-")
        self.assertNotContains(response, "Descripción privada")
        for req in (self.abiertas[0], self.pendiente):
            self.assertEqual(self.client.get(reverse("detalle_tecnico", args=[req.pk])).status_code, 403)
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("detalle_tecnico", args=[self.abiertas[0].pk])).status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("detalle_tecnico", args=[self.abiertas[0].pk])).status_code, 200)

    def test_funcionario_asignado_por_error_no_puede_modificar_solicitudes(self):
        req = self.abiertas[0]
        req.responsable = self.funcionario
        req.save()
        self.client.force_login(self.funcionario)
        for ruta, datos in (("iniciar_atencion", {}), ("agregar_observacion", {"observacion": "No permitido"}),
                            ("resolver_requerimiento", {"solucion": "No permitido"}), ("cerrar_requerimiento", {})):
            self.assertEqual(self.client.post(reverse(ruta, args=[req.pk]), datos).status_code, 403)

    def test_tecnico_puede_tomar_pendiente_y_entonces_ver_detalle(self):
        self.client.force_login(self.reemplazo)
        self.client.post(reverse("asignarme_requerimiento", args=[self.pendiente.pk]))
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.responsable, self.reemplazo)
        self.assertEqual(self.client.get(reverse("detalle_tecnico", args=[self.pendiente.pk])).status_code, 200)

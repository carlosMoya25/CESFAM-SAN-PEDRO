from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventario.models import Articulo, CategoriaArticulo, MovimientoInventario, RecursoRequerimiento, StockAnexo
from inventario.services import registrar_entrada, registrar_recurso_requerimiento
from organizacion.models import Anexo
from requerimientos.models import EstadoRequerimiento, HistorialRequerimiento, Prioridad, Requerimiento, TipoRequerimiento
from usuarios.models import HistorialSeguridad


class AdminTrazabilidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(email="admin-trazabilidad@example.com")
        categoria = CategoriaArticulo.objects.create(nombre="Materiales")
        articulo = Articulo.objects.create(nombre="Cable", categoria=categoria)
        anexo = Anexo.objects.create(nombre="Anexo de prueba")
        entrada = registrar_entrada(usuario=cls.admin, anexo=anexo, articulo=articulo, cantidad=10)
        requerimiento = Requerimiento.objects.create(
            titulo="Equipo sin red", descripcion="Revisar conexión", solicitante=cls.admin,
            responsable=cls.admin, anexo=anexo, estado=EstadoRequerimiento.objects.get(nombre="Asignado"),
            prioridad=Prioridad.objects.get(nombre="Media"), tipo_requerimiento=TipoRequerimiento.objects.get(nombre="Hardware"),
        )
        recurso = registrar_recurso_requerimiento(requerimiento=requerimiento, articulo=articulo, cantidad=2, usuario=cls.admin)
        historial = HistorialRequerimiento.objects.create(
            requerimiento=requerimiento, usuario=cls.admin, estado_nuevo=requerimiento.estado, accion="Requerimiento asignado",
        )
        seguridad = HistorialSeguridad.objects.create(
            tipo_accion="OTRO", usuario_afectado=cls.admin, email_afectado=cls.admin.email,
            realizado_por=cls.admin, descripcion="Evento de prueba",
        )
        cls.registros = (
            (StockAnexo, StockAnexo.objects.get(articulo=articulo, anexo=anexo).pk,
             {"articulo": articulo.pk, "anexo": anexo.pk, "cantidad": 999}),
            (MovimientoInventario, entrada.pk, {"motivo": "Alterado"}),
            (RecursoRequerimiento, recurso.pk, {"cantidad": 999}),
            (Requerimiento, requerimiento.pk, {"titulo": "Alterado"}),
            (HistorialRequerimiento, historial.pk, {"accion": "Alterada"}),
            (HistorialSeguridad, seguridad.pk, {"descripcion": "Alterada"}),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def url_admin(self, modelo, accion, pk=None):
        return reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_{accion}", args=[pk] if pk else None)

    def test_superusuario_puede_consultar_sin_acciones_de_guardado_o_borrado(self):
        for modelo, pk, _ in self.registros:
            with self.subTest(modelo=modelo.__name__):
                listado = self.client.get(self.url_admin(modelo, "changelist"))
                self.assertEqual(listado.status_code, 200)
                acciones = listado.context["action_form"]
                self.assertFalse(acciones and "delete_selected" in dict(acciones.fields["action"].choices))
                detalle = self.client.get(self.url_admin(modelo, "change", pk))
                self.assertEqual(detalle.status_code, 200)
                self.assertNotContains(detalle, 'name="_save"')

    def test_post_directo_no_crea_ni_modifica_registros(self):
        for modelo, pk, datos in self.registros:
            with self.subTest(modelo=modelo.__name__):
                anterior = list(modelo.objects.order_by("pk").values())
                self.assertEqual(self.client.post(self.url_admin(modelo, "add"), datos).status_code, 403)
                self.assertEqual(self.client.post(self.url_admin(modelo, "change", pk), datos).status_code, 403)
                self.assertEqual(list(modelo.objects.order_by("pk").values()), anterior)

    def test_borrado_directo_y_masivo_conservan_registros_y_saldos(self):
        saldos = list(StockAnexo.objects.values())
        for modelo, pk, _ in self.registros:
            with self.subTest(modelo=modelo.__name__):
                anterior = list(modelo.objects.order_by("pk").values())
                self.assertEqual(self.client.get(self.url_admin(modelo, "delete", pk)).status_code, 403)
                self.assertEqual(self.client.post(self.url_admin(modelo, "delete", pk), {"post": "yes"}).status_code, 403)
                self.client.post(self.url_admin(modelo, "changelist"), {
                    "action": "delete_selected", "_selected_action": [pk], "post": "yes",
                })
                self.assertEqual(list(modelo.objects.order_by("pk").values()), anterior)
        self.assertEqual(list(StockAnexo.objects.values()), saldos)

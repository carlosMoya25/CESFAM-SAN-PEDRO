from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from farmacia.models import ImportacionMedicamentos, MovimientoFarmacia
from organizacion.models import Anexo
from requerimientos.models import EstadoRequerimiento, HistorialRequerimiento, Prioridad, Requerimiento, TipoRequerimiento
from usuarios.models import HistorialAdministracion
from . import privacidad
from .conservacion import guardar_regla, simular_conservacion
from .models import (CambioReglaConservacion, ConstanciaPrivacidad, ReglaConservacion,
                     SimulacionConservacion, SolicitudDerecho)


class ConservacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin = Usuario.objects.create_user(email="admin-conservacion@example.com")
        cls.admin.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        cls.tecnico = Usuario.objects.create_user(email="tecnico-conservacion@example.com")
        cls.tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        cls.usuario = Usuario.objects.create_user(email="usuario-conservacion@example.com")
        cls.ahora = timezone.now()
        cls.antigua = cls.ahora - timedelta(days=60)
        cls.reciente = cls.ahora - timedelta(days=1)

    def regla(self, categoria, dias=30, revision=0, fundamento="Referencia institucional de prueba"):
        return guardar_regla(usuario=self.admin, categoria=categoria, dias=dias, revision=revision, fundamento=fundamento)

    def informe(self, categoria):
        self.regla(categoria)
        with patch("core.conservacion.timezone.now", return_value=self.ahora):
            informe = simular_conservacion(usuario=self.admin)
        return next(f for f in informe.resultado["filas"] if f["categoria"] == categoria)

    def test_sin_plazos_no_crea_informe_ni_asume_defaults(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("panel_conservacion")), "Sin definir", count=7)
        self.assertFalse(ReglaConservacion.objects.exists())
        with self.assertRaises(ValidationError):
            simular_conservacion(usuario=self.admin)
        self.assertFalse(SimulacionConservacion.objects.exists())

    def test_propuesta_auditada_y_control_de_revision(self):
        regla = self.regla("BORRADORES")
        self.assertEqual(regla.revision, 1)
        cambio = CambioReglaConservacion.objects.get()
        self.assertEqual(cambio.realizado_por, self.admin)
        self.assertIsNone(cambio.anterior["dias"])
        self.assertEqual(cambio.nuevo["dias"], 30)
        with self.assertRaises(ValidationError):
            self.regla("BORRADORES", dias=90)
        self.regla("BORRADORES", dias=None, revision=1, fundamento="Pendiente de definición")
        self.assertIsNone(ReglaConservacion.objects.get().dias)
        self.assertEqual(CambioReglaConservacion.objects.count(), 2)

    def test_validacion_de_plazo_fundamento_y_categoria(self):
        for dias in (0, -1, 36501):
            with self.assertRaises(ValidationError):
                self.regla("BORRADORES", dias=dias)
        with self.assertRaises(ValidationError):
            self.regla("BORRADORES", fundamento="")
        with self.assertRaises(ValidationError):
            self.regla("NO_EXISTE")
        self.assertFalse(ReglaConservacion.objects.exists())

    def test_borradores_excluye_recibidas_y_no_modifica_contenidos(self):
        solicitudes = []
        for estado, fecha in (("BORRADOR", self.antigua), ("BORRADOR", self.reciente), ("RECIBIDA", self.antigua)):
            sol = SolicitudDerecho.objects.create(solicitante=self.usuario, tipo="ACCESO", estado=estado,
                                                 detalle="Contenido privado que no debe aparecer en el informe")
            SolicitudDerecho.objects.filter(pk=sol.pk).update(actualizada_at=fecha)
            solicitudes.append(sol)
        antes = list(SolicitudDerecho.objects.values())
        fila = self.informe("BORRADORES")
        self.assertEqual((fila["total"], fila["en_alcance"], fila["antiguos"]), (3, 2, 1))
        self.assertEqual(antes, list(SolicitudDerecho.objects.values()))
        resultado = str(SimulacionConservacion.objects.get().resultado)
        self.assertNotIn(self.usuario.email, resultado)
        self.assertNotIn("Contenido privado", resultado)
        self.assertNotIn(str(solicitudes[0].identificador), resultado)

    def test_derechos_respondidos_desde_respuesta_no_desde_creacion(self):
        for estado, fecha in (("RESPONDIDA", self.antigua), ("RESPONDIDA", self.reciente), ("RECIBIDA", None)):
            SolicitudDerecho.objects.create(solicitante=self.usuario, tipo="ACCESO", detalle="Datos de prueba",
                                           estado=estado, respondida_at=fecha)
        fila = self.informe("DERECHOS")
        self.assertEqual((fila["en_alcance"], fila["antiguos"]), (2, 1))

    def test_importadas_o_pendientes_con_movimientos_quedan_fuera(self):
        for estado, con_movimiento in (("PENDIENTE", False), ("PENDIENTE", True), ("IMPORTADA", False)):
            imp = ImportacionMedicamentos.objects.create(usuario=self.usuario, nombre_archivo="archivo.csv",
                                                         archivo_sha256="a" * 64, estado=estado, filas=[{"privado": "No divulgar"}])
            ImportacionMedicamentos.objects.filter(pk=imp.pk).update(creada_at=self.antigua)
            if con_movimiento:
                MovimientoFarmacia.objects.create(usuario=self.usuario, tipo="ENTRADA", importacion=imp)
        antes = list(ImportacionMedicamentos.objects.values())
        fila = self.informe("IMPORTACIONES")
        self.assertEqual((fila["en_alcance"], fila["antiguos"]), (1, 1))
        self.assertEqual(antes, list(ImportacionMedicamentos.objects.values()))
        self.assertNotIn("No divulgar", str(SimulacionConservacion.objects.get().resultado))

    def test_sesiones_se_cuentan_desde_vencimiento_y_no_se_borran(self):
        for i, fecha in enumerate((self.antigua, self.reciente, self.ahora + timedelta(days=1))):
            Session.objects.create(session_key=f"sesionconservacion{i:014d}", session_data="Datos privados de prueba", expire_date=fecha)
        antes = list(Session.objects.values())
        fila = self.informe("SESIONES")
        self.assertEqual((fila["total"], fila["en_alcance"], fila["antiguos"]), (3, 2, 1))
        self.assertEqual(antes, list(Session.objects.values()))

    def test_requerimientos_excluye_abiertos_y_actividad_reciente_en_historial(self):
        anexo = Anexo.objects.create(nombre="Pruebas de conservación")
        for estado, historial_reciente in (("Cerrado", False), ("Cerrado", True), ("Cancelado", False), ("Asignado", False)):
            req = Requerimiento.objects.create(titulo="Requerimiento privado", descripcion="Contenido privado",
                solicitante=self.usuario, anexo=anexo, estado=EstadoRequerimiento.objects.get(nombre=estado),
                prioridad=Prioridad.objects.first(), tipo_requerimiento=TipoRequerimiento.objects.first())
            Requerimiento.objects.filter(pk=req.pk).update(updated_at=self.antigua)
            if historial_reciente:
                HistorialRequerimiento.objects.create(requerimiento=req, usuario=self.usuario, accion="Actividad reciente")
        fila = self.informe("REQUERIMIENTOS")
        self.assertEqual((fila["en_alcance"], fila["antiguos"]), (3, 2))

    def test_constancias_actuales_no_se_incluyen_aunque_sean_antiguas(self):
        for version, huella, fecha in ((privacidad.VERSION, privacidad.HUELLA, self.antigua),
                                       ("anterior", "b" * 64, self.antigua), ("otra", "c" * 64, self.reciente)):
            constancia = ConstanciaPrivacidad.objects.create(usuario=self.usuario, version=version, huella=huella,
                                                              texto="Aviso de prueba", declaracion="Lectura de prueba")
            ConstanciaPrivacidad.objects.filter(pk=constancia.pk).update(fecha=fecha)
        fila = self.informe("CONSTANCIAS")
        self.assertEqual((fila["en_alcance"], fila["antiguos"]), (2, 1))

    def test_cuentas_sin_fecha_de_baja_no_se_clasifican_por_antiguedad(self):
        for nombre, activo, fecha in (("antiguo", False, self.antigua), ("reciente", False, self.reciente),
                                     ("sinfecha", False, None), ("reactivado", True, self.antigua)):
            usuario = get_user_model().objects.create_user(email=f"{nombre}@example.com", is_active=activo)
            if fecha:
                evento = HistorialAdministracion.objects.create(accion="DESACTIVAR_USUARIO", administrador=self.admin,
                                                                 usuario_afectado=usuario, descripcion="Baja de prueba")
                HistorialAdministracion.objects.filter(pk=evento.pk).update(fecha=fecha)
        fila = self.informe("CUENTAS")
        self.assertEqual((fila["en_alcance"], fila["antiguos"], fila["sin_fecha"]), (3, 1, 1))

    def test_informe_conserva_version_de_regla_y_fecha_de_corte(self):
        regla = self.regla("SESIONES")
        informe = simular_conservacion(usuario=self.admin)
        copia = informe.resultado.copy()
        self.regla("SESIONES", dias=90, revision=regla.revision)
        informe.refresh_from_db()
        self.assertEqual(informe.resultado, copia)
        fila = next(f for f in informe.resultado["filas"] if f["categoria"] == "SESIONES")
        self.assertEqual((fila["dias"], fila["revision"]), (30, 1))
        self.assertTrue(fila["fecha_corte"])
        self.assertEqual(sum(f["evaluada"] for f in informe.resultado["filas"]), 1)

    def test_rutas_solo_administracion_y_csrf(self):
        self.regla("BORRADORES")
        informe = simular_conservacion(usuario=self.admin)
        rutas = [reverse("panel_conservacion"), reverse("editar_regla_conservacion", args=["BORRADORES"]),
                 reverse("detalle_simulacion_conservacion", args=[informe.pk])]
        for usuario in (self.usuario, self.tecnico):
            self.client.force_login(usuario)
            for ruta in rutas:
                self.assertEqual(self.client.get(ruta).status_code, 403)
            self.assertEqual(self.client.post(reverse("simular_conservacion")).status_code, 403)
            with self.assertRaises(PermissionDenied):
                simular_conservacion(usuario=usuario)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post(reverse("simular_conservacion")).status_code, 403)
        self.assertEqual(cliente.post(reverse("editar_regla_conservacion", args=["BORRADORES"]), {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("panel_conservacion")).status_code, 302)

    def test_interfaz_guardar_simular_y_ver_informe_sin_accion_de_borrado(self):
        self.client.force_login(self.admin)
        url = reverse("editar_regla_conservacion", args=["BORRADORES"])
        self.assertEqual(self.client.post(url, {"dias": 30, "revision": 0, "fundamento": "Política en revisión"}).status_code, 302)
        response = self.client.post(reverse("simular_conservacion"))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertContains(response, "No se eliminó ni modificó ningún registro evaluado")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(self.client.get(url), "Historial de la propuesta")
        self.assertEqual(self.client.get(reverse("simular_conservacion")).status_code, 405)
        self.assertEqual(self.client.get(reverse("editar_regla_conservacion", args=["OTRA"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("detalle_simulacion_conservacion", args=[999999])).status_code, 404)

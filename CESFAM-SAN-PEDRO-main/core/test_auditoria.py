import io
import json
import logging
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from inventario.models import Articulo, CategoriaArticulo, StockAnexo
from inventario.services import registrar_entrada
from organizacion.models import Anexo
from .auditoria import contexto_auditoria
from .logging import FormatoSeguroJSON
from .models import EventoAuditoria, EventoSolicitudDerecho, SolicitudDerecho


Usuario = get_user_model()


class AuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(email="auditoria-admin@example.com", is_superuser=True, is_staff=True)
        cls.tecnico = Usuario.objects.create_user(email="auditoria-tecnico@example.com")
        cls.tecnico.groups.add(Group.objects.get(name="Técnico TI"))
        cls.funcionario = Usuario.objects.create_user(email="auditoria-funcionario@example.com")
        cls.categoria = CategoriaArticulo.objects.create(nombre="Materiales")
        cls.articulo = Articulo.objects.create(nombre="Cable", categoria=cls.categoria)
        cls.anexo = Anexo.objects.create(nombre="Anexo auditoría")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_cambio_seguro_conserva_actor_y_valores_operativos_sin_textos(self):
        with contexto_auditoria(usuario=self.admin):
            self.articulo.stock_minimo = 12
            self.articulo.descripcion = "diagnostico-privado-735"
            self.articulo.save()
        evento = EventoAuditoria.objects.filter(modelo="inventario.articulo", objeto_id=str(self.articulo.pk), accion="MODIFICAR").latest("pk")
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertEqual(evento.antes["stock_minimo"], 0)
        self.assertEqual(evento.despues["stock_minimo"], 12)
        self.assertIn("descripcion", evento.campos)
        self.assertNotIn("diagnostico-privado-735", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_password_correo_y_datos_personales_no_se_copian(self):
        with contexto_auditoria(usuario=self.admin):
            self.funcionario.email = "correo-secreto-783@example.com"
            self.funcionario.telefono = "telefono-secreto-783"
            self.funcionario.set_password("Password-privado-783!")
            self.funcionario.save()
        texto = json.dumps(list(EventoAuditoria.objects.values()), default=str)
        for privado in (self.funcionario.email, self.funcionario.telefono, "Password-privado-783!", self.funcionario.password):
            self.assertNotIn(privado, texto)
        self.assertTrue(EventoAuditoria.objects.filter(modelo="usuarios.usuario", accion="MODIFICAR", objeto_id=str(self.funcionario.pk)).exists())

    def test_movimiento_de_servicio_tambien_se_audita_sin_peticion_web(self):
        with contexto_auditoria(usuario=self.admin, origen="COMANDO"):
            movimiento = registrar_entrada(usuario=self.admin, articulo=self.articulo, anexo=self.anexo, cantidad=7)
        evento = EventoAuditoria.objects.filter(modelo="inventario.detallemovimiento", despues__movimiento_id=movimiento.pk).get()
        self.assertEqual(evento.despues["cantidad"], 7)
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertEqual(evento.origen, "COMANDO")
        self.assertEqual(StockAnexo.objects.get(articulo=self.articulo, anexo=self.anexo).cantidad, 7)

    def test_roles_y_permisos_m2m_se_auditan(self):
        rol = Group.objects.get(name="Encargado de Inventario")
        with contexto_auditoria(usuario=self.admin):
            self.funcionario.groups.add(rol)
            self.funcionario.groups.remove(rol)
            self.funcionario.groups.add(rol)
            self.funcionario.groups.clear()
        eventos = EventoAuditoria.objects.filter(modelo="usuarios.usuario", objeto_id=str(self.funcionario.pk), accion="CAMBIAR_ROLES")
        self.assertEqual(eventos.count(), 4)
        self.assertEqual(eventos.latest("pk").antes["groups"], [rol.pk])
        self.assertEqual(eventos.latest("pk").despues["groups"], [])

    def test_rollback_no_conserva_cambio_ni_evento_completado(self):
        cuenta = EventoAuditoria.objects.count()
        with self.assertRaises(RuntimeError):
            with transaction.atomic(), contexto_auditoria(usuario=self.admin):
                self.articulo.stock_minimo = 99
                self.articulo.save()
                raise RuntimeError("revertir")
        self.articulo.refresh_from_db()
        self.assertEqual(self.articulo.stock_minimo, 0)
        self.assertEqual(EventoAuditoria.objects.count(), cuenta)

    def test_privacidad_registra_referencia_sin_contenido_de_solicitud(self):
        with contexto_auditoria(usuario=self.funcionario):
            solicitud = SolicitudDerecho.objects.create(solicitante=self.funcionario, tipo="ACCESO", detalle="antecedentes-muy-privados-836")
            EventoSolicitudDerecho.objects.create(solicitud=solicitud, accion="CREADA", revision=1, realizado_por=self.funcionario)
        evento = EventoAuditoria.objects.filter(modelo="core.eventosolicitudderecho").get()
        self.assertEqual(evento.despues["solicitud_id"], solicitud.pk)
        self.assertNotIn("antecedentes-muy-privados-836", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_peticion_guarda_ruta_normalizada_y_uuid_sin_parametros(self):
        response = self.client.get(reverse("inventario:articulos"), {"buscar": "busqueda-privada-345"})
        identificador = uuid.UUID(response["X-Request-ID"])
        evento = EventoAuditoria.objects.get(solicitud_id=identificador, accion="CONSULTAR")
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertEqual(evento.vista, "inventario:articulos")
        self.assertEqual(evento.estado_http, 200)
        self.assertGreaterEqual(evento.duracion_ms, 0)
        self.assertNotIn("busqueda-privada-345", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_formulario_invalido_es_rechazado_sin_inventar_cambio(self):
        antes = CategoriaArticulo.objects.count()
        response = self.client.post(reverse("inventario:crear_categoria"), {"nombre": "", "descripcion": "texto-privado-557"})
        self.assertEqual(response.status_code, 200)
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"], accion="SOLICITUD_HTTP")
        self.assertEqual(evento.resultado, "RECHAZADA")
        self.assertEqual(CategoriaArticulo.objects.count(), antes)
        self.assertNotIn("texto-privado-557", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_login_logout_y_fallo_no_filtran_credenciales_ni_arrastran_actor(self):
        self.funcionario.set_password("Temporal-segura-557!")
        self.funcionario.save()
        cliente = Client()
        cliente.post(reverse("login"), {"username": self.funcionario.email, "password": "Incorrecta-557!"})
        self.assertTrue(EventoAuditoria.objects.filter(accion="ACCESO_FALLIDO", resultado="RECHAZADA").exists())
        response = cliente.post(reverse("login"), {"username": self.funcionario.email, "password": "Temporal-segura-557!"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EventoAuditoria.objects.filter(accion="INICIO_SESION", usuario=self.funcionario).exists())
        cliente.post(reverse("logout"))
        self.assertTrue(EventoAuditoria.objects.filter(accion="FIN_SESION", usuario=self.funcionario).exists())
        response = Client().get(reverse("aviso_privacidad"))
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"], accion="CONSULTAR")
        self.assertIsNone(evento.usuario_id)
        texto = json.dumps(list(EventoAuditoria.objects.values()), default=str)
        self.assertNotIn("Incorrecta-557!", texto)
        self.assertNotIn("Temporal-segura-557!", texto)

    def test_denegacion_y_ruta_inexistente_no_guardan_url_atacante(self):
        self.client.force_login(self.funcionario)
        response = self.client.get(reverse("panel_auditoria"))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(EventoAuditoria.objects.filter(solicitud_id=response["X-Request-ID"], resultado="RECHAZADA").exists())
        response = self.client.get("/token-privado-836/no-existe/")
        self.assertEqual(response.status_code, 404)
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"])
        self.assertEqual(evento.ruta, "")
        self.assertNotIn("token-privado-836", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_navegacion_sigue_disponible_si_falla_persistencia_de_auditoria(self):
        with patch("core.auditoria.EventoAuditoria.objects.create", side_effect=RuntimeError("clave-interna-937")):
            with self.assertLogs("cesfam", level="WARNING") as salida:
                response = self.client.get(reverse("aviso_privacidad"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("clave-interna-937", str(salida.output))

    def test_panel_ambos_roles_filtros_invalidos_y_solo_lectura(self):
        objetivo = EventoAuditoria.objects.create(modulo="inventario", accion="CREAR", modelo="inventario.articulo", objeto_id="98765", usuario=self.admin)
        for usuario in (self.admin, self.tecnico):
            self.client.force_login(usuario)
            response = self.client.get(reverse("panel_auditoria"), {"modulo": "inventario", "objeto_id": "98765"})
            self.assertContains(response, "98765")
            self.assertContains(response, reverse("detalle_auditoria", args=[objetivo.pk]))
            self.assertEqual(self.client.get(reverse("detalle_auditoria", args=[objetivo.pk])).status_code, 200)
            self.assertEqual(self.client.post(reverse("panel_auditoria"), {"borrar": objetivo.pk}).status_code, 405)
        response = self.client.get(reverse("panel_auditoria"), {"desde": "fecha-invalida"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(len(response.context["eventos"]), 0)
        self.assertTrue(EventoAuditoria.objects.filter(pk=objetivo.pk).exists())
        self.assertTrue(EventoAuditoria.objects.filter(vista="panel_auditoria", usuario=self.tecnico).exists())

    def test_funcionario_anonimo_e_inactivo_no_consultan_panel(self):
        self.client.force_login(self.funcionario)
        self.assertEqual(self.client.get(reverse("panel_auditoria")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("panel_auditoria")).status_code, 302)
        self.tecnico.is_active = False
        self.tecnico.save()
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("panel_auditoria")).status_code, 302)

    def test_admin_consulta_sin_poder_modificar_ni_borrar_auditoria(self):
        evento = EventoAuditoria.objects.first()
        base = "admin:core_eventoauditoria_"
        self.assertEqual(self.client.get(reverse(base + "changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse(base + "change", args=[evento.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse(base + "change", args=[evento.pk]), {"accion": "ALTERADA"}).status_code, 403)
        self.assertEqual(self.client.post(reverse(base + "delete", args=[evento.pk]), {"post": "yes"}).status_code, 403)
        self.client.post(reverse(base + "changelist"), {"action": "delete_selected", "_selected_action": [evento.pk], "post": "yes"})
        self.assertTrue(EventoAuditoria.objects.filter(pk=evento.pk).exists())

    def test_formato_tecnico_excluye_mensajes_excepciones_y_payloads(self):
        try:
            raise ValueError("password=secreto-888&token=privado-888")
        except ValueError:
            import sys
            record = logging.LogRecord("django.request", logging.ERROR, __file__, 200, "correo@example.com?token=privado-888", (), sys.exc_info())
        record.request = object()
        record.password = "secreto-888"
        resultado = FormatoSeguroJSON().format(record)
        datos = json.loads(resultado)
        self.assertEqual(datos["excepcion"], "ValueError")
        for privado in ("secreto-888", "privado-888", "correo@example.com"):
            self.assertNotIn(privado, resultado)


    def test_detalle_de_movimiento_atribuye_actor_al_ejecutar_servicio_directo(self):
        movimiento = registrar_entrada(usuario=self.admin, articulo=self.articulo, anexo=self.anexo, cantidad=5)
        evento = EventoAuditoria.objects.get(modelo="inventario.detallemovimiento", despues__movimiento_id=movimiento.pk)
        self.assertEqual(evento.usuario_id, self.admin.pk)

    def test_consulta_de_ficha_guarda_id_seguro_sin_parametros(self):
        response = self.client.get(reverse("inventario:editar_articulo", args=[self.articulo.pk]), {"token": "privado-937"})
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"], accion="CONSULTAR")
        self.assertEqual(evento.objeto_id, str(self.articulo.pk))
        self.assertNotIn("privado-937", json.dumps(list(EventoAuditoria.objects.values()), default=str))

    def test_ti_con_staff_consulta_admin_y_otro_staff_no_aunque_tenga_permiso(self):
        self.tecnico.is_staff = True
        self.tecnico.save()
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(reverse("admin:core_eventoauditoria_changelist")).status_code, 200)
        self.funcionario.is_staff = True
        self.funcionario.save()
        self.funcionario.user_permissions.add(Permission.objects.get(codename="view_eventoauditoria"))
        self.client.force_login(self.funcionario)
        self.assertEqual(self.client.get(reverse("admin:core_eventoauditoria_changelist")).status_code, 403)

    def test_filtro_de_fecha_usa_dia_completo_de_chile(self):
        from datetime import datetime, timezone as utc
        eventos = [EventoAuditoria.objects.create(modulo="inventario", accion="CREAR", objeto_id="hora-chile") for _ in range(4)]
        fechas = [datetime(2026, 10, 26, 2, 59, tzinfo=utc.utc), datetime(2026, 10, 26, 3, 0, tzinfo=utc.utc),
                  datetime(2026, 10, 27, 2, 59, tzinfo=utc.utc), datetime(2026, 10, 27, 3, 0, tzinfo=utc.utc)]
        for evento, fecha in zip(eventos, fechas):
            EventoAuditoria.objects.filter(pk=evento.pk).update(fecha=fecha)
        response = self.client.get(reverse("panel_auditoria"), {"desde": "2026-10-26", "hasta": "2026-10-26", "objeto_id": "hora-chile"})
        self.assertEqual([e.pk for e in response.context["eventos"]], [eventos[2].pk, eventos[1].pk])

    def test_fallo_500_se_correlaciona_sin_imprimir_secreto(self):
        from django.http import HttpResponse
        from .auditoria_middleware import AuditoriaMiddleware
        from django.test import RequestFactory
        def respuesta_error(request):
            logging.getLogger("django.request").error("password=privado-993", exc_info=ValueError("token=privado-993"))
            return HttpResponse(status=500)
        request = RequestFactory().get("/codigo-no-copiado/?token=privado-993")
        request.user = self.admin
        request.resolver_match = None
        salida = io.StringIO()
        handler = logging.StreamHandler(salida)
        handler.setFormatter(FormatoSeguroJSON())
        logger = logging.getLogger("django.request")
        logger.addHandler(handler)
        try:
            response = AuditoriaMiddleware(respuesta_error)(request)
        finally:
            logger.removeHandler(handler)
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"])
        self.assertEqual(evento.resultado, "FALLIDA")
        self.assertEqual(json.loads(salida.getvalue())["solicitud_id"], response["X-Request-ID"])
        self.assertNotIn("privado-993", salida.getvalue())


    def test_fallo_de_respaldo_no_deja_archivos_ni_registro(self):
        import tempfile
        from pathlib import Path
        from .test_respaldos import ProcesoDump
        from .models import RespaldoBase
        from .respaldos import crear_respaldo
        meta = {"base": "prueba", "motor": "mariadb", "version": "11.4.5", "imagen": "mariadb:11.4", "filas": {"tabla": 0}}
        sql = b"CREATE TABLE `tabla` (id integer);\nINSERT INTO `tabla` VALUES (1);\n"
        with tempfile.TemporaryDirectory() as temporal:
            root = Path(temporal) / "copias"
            with override_settings(BACKUP_ROOT=root, BACKUP_KEY_FILE=Path(temporal) / "claves" / "backup.key"), \
                 patch("core.respaldos.metadatos_origen", return_value=meta), \
                 patch("core.respaldos.shutil.which", return_value="/usr/bin/mysqldump"), \
                 patch("core.respaldos.subprocess.Popen", return_value=ProcesoDump(sql)), \
                 patch("core.auditoria.EventoAuditoria.objects.create", side_effect=RuntimeError("auditoria no disponible")):
                with self.assertRaises(RuntimeError):
                    crear_respaldo(crear_clave=True)
            self.assertEqual(list(root.iterdir()), [])
            self.assertFalse(RespaldoBase.objects.exists())

    @override_settings(BACKUP_WORKER_ID="auditoria-ejecutor")
    def test_ejecucion_interrumpida_tiene_evento_aunque_no_haya_copia_nueva(self):
        from .models import EjecucionProgramadaRespaldo
        from .respaldo_programacion import ejecutar_turno
        ejecucion = EjecucionProgramadaRespaldo.objects.create(ejecutor="auditoria-ejecutor", politica_revision=999,
            programada_para=timezone.now(), estado="EN_CURSO")
        with patch("core.respaldo_programacion.leer_clave", return_value=b"x" * 32), \
             patch("core.respaldo_programacion.shutil.which", return_value="/usr/bin/mariadb-dump"):
            ejecutar_turno()
        ejecucion.refresh_from_db()
        self.assertEqual(ejecucion.estado, "INTERRUMPIDA")
        evento = EventoAuditoria.objects.get(modelo="core.ejecucionprogramadarespaldo", objeto_id=str(ejecucion.pk), accion="MODIFICAR")
        self.assertEqual(evento.despues["estado"], "INTERRUMPIDA")
        self.assertEqual(evento.resultado, "FALLIDA")

    def test_comando_fallido_guarda_origen_y_no_expone_excepcion(self):
        from django.core.management import call_command, CommandError
        with patch("core.management.commands.crear_respaldo.crear_respaldo", side_effect=ValueError("password=privado-987")):
            with self.assertRaises(CommandError) as error:
                call_command("crear_respaldo", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertNotIn("privado-987", str(error.exception))
        evento = EventoAuditoria.objects.filter(accion="COMANDO_FINALIZADO").get()
        self.assertEqual(evento.resultado, "FALLIDA")
        self.assertEqual(evento.origen, "COMANDO")
        self.assertNotIn("privado-987", json.dumps(list(EventoAuditoria.objects.values()), default=str))


    def test_credenciales_rechazadas_marcan_tambien_solicitud_http(self):
        cliente = Client()
        response = cliente.post(reverse("login"), {"username": self.funcionario.email, "password": "credencial-incorrecta-433"})
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"], accion="SOLICITUD_HTTP")
        self.assertEqual(evento.resultado, "RECHAZADA")

    def test_formulario_requerimiento_invalido_no_se_confunde_con_finalizado(self):
        response = self.client.post(reverse("crear_requerimiento"), {"titulo": "", "descripcion": "dato-privado-433"})
        evento = EventoAuditoria.objects.get(solicitud_id=response["X-Request-ID"], accion="SOLICITUD_HTTP")
        self.assertEqual(evento.resultado, "RECHAZADA")
        self.assertNotIn("dato-privado-433", json.dumps(list(EventoAuditoria.objects.values()), default=str))


    def test_guardado_parcial_solo_audita_campos_que_se_persistieron(self):
        with contexto_auditoria(usuario=self.admin):
            self.articulo.stock_minimo = 50
            self.articulo.activo = False
            self.articulo.save(update_fields=["activo"])
        evento = EventoAuditoria.objects.get(modelo="inventario.articulo", objeto_id=str(self.articulo.pk), accion="MODIFICAR")
        self.assertEqual(evento.campos, ["activo"])
        self.assertEqual(evento.despues, {"activo": False})
        self.articulo.refresh_from_db()
        self.assertEqual(self.articulo.stock_minimo, 0)

    def test_borrar_grupo_registra_retirada_de_roles_de_sus_usuarios(self):
        grupo = Group.objects.create(name="Rol de auditoría")
        self.funcionario.groups.add(grupo)
        with contexto_auditoria(usuario=self.admin):
            grupo.delete()
        evento = EventoAuditoria.objects.filter(modelo="usuarios.usuario", objeto_id=str(self.funcionario.pk), accion="CAMBIAR_ROLES").latest("pk")
        self.assertEqual(evento.despues["groups"], [])
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertFalse(self.funcionario.groups.exists())


    def test_borrado_masivo_de_grupos_refleja_membresias_finales_reales(self):
        grupos = [Group.objects.create(name="Rol auditoría A"), Group.objects.create(name="Rol auditoría B")]
        self.funcionario.groups.add(*grupos)
        with contexto_auditoria(usuario=self.admin):
            Group.objects.filter(pk__in=[g.pk for g in grupos]).delete()
        eventos = EventoAuditoria.objects.filter(modelo="usuarios.usuario", objeto_id=str(self.funcionario.pk), accion="CAMBIAR_ROLES", usuario=self.admin)
        self.assertTrue(eventos.exists())
        for evento in eventos:
            self.assertEqual(evento.despues["groups"], [])


    def test_formateador_funciona_antes_de_inicializar_django(self):
        import subprocess
        import sys
        codigo = "import logging; from core.logging import FormatoSeguroJSON; print(FormatoSeguroJSON().format(logging.LogRecord('inicio',30,'archivo.py',1,'mensaje privado',(),None)))"
        resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=10)
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(json.loads(resultado.stdout)["logger"], "inicio")
        self.assertNotIn("mensaje privado", resultado.stdout)


    def test_responsable_muestra_correo_y_distingue_eventos_sin_sesion(self):
        casos = [
            ({"usuario": self.funcionario, "origen": "WEB", "accion": "INICIO_SESION"}, self.funcionario.email),
            ({"origen": "WEB", "accion": "CONSULTAR", "vista": "google_login"}, "Sesión no iniciada"),
            ({"origen": "COMANDO", "accion": "COMANDO_INICIADO"}, "Comando sin usuario identificado"),
            ({"origen": "SISTEMA", "accion": "CREAR"}, "Proceso del sistema"),
        ]
        for datos, etiqueta in casos:
            with self.subTest(origen=datos["origen"], accion=datos["accion"]):
                evento = EventoAuditoria.objects.create(modulo="usuarios", **datos)
                detalle = self.client.get(reverse("detalle_auditoria", args=[evento.pk]))
                self.assertContains(detalle, etiqueta)
                listado = self.client.get(reverse("panel_auditoria"), {"solicitud_id": str(evento.solicitud_id)})
                self.assertContains(listado, etiqueta)
                self.assertNotContains(detalle, "Sin usuario autenticado")


class AuditoriaAtomicidadTests(TransactionTestCase):
    def test_fallo_auditoria_revierte_creacion_catalogo_en_autocommit_real(self):
        usuario = Usuario.objects.create_user(email="autocommit@example.com", is_superuser=True)
        self.client.force_login(usuario)
        with patch("core.auditoria.EventoAuditoria.objects.create", side_effect=RuntimeError("auditoria no disponible")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("inventario:crear_categoria"), {"nombre": "No persistir", "activo": "on"})
        self.assertFalse(CategoriaArticulo.objects.filter(nombre="No persistir").exists())

    def test_fallo_del_diagnostico_no_convierte_un_cambio_confirmado_en_error(self):
        with patch("core.auditoria.logger.log", side_effect=RuntimeError("salida de diagnóstico no disponible")):
            with transaction.atomic():
                categoria = CategoriaArticulo.objects.create(nombre="Cambio confirmado")
        self.assertTrue(CategoriaArticulo.objects.filter(pk=categoria.pk).exists())
        self.assertTrue(EventoAuditoria.objects.filter(modelo="inventario.categoriaarticulo", objeto_id=str(categoria.pk)).exists())

from datetime import datetime, time, timedelta, timezone as utc
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (CambioProgramacionRespaldos, EjecucionProgramadaRespaldo,
                     PoliticaRespaldos, ProgramacionRespaldos, RespaldoBase)
from .respaldo_crypto import ErrorRespaldo
from .respaldo_forms import PoliticaRespaldosForm
from .respaldo_politica import guardar_politica
from .respaldo_programacion import (CHILE, bloqueo_programador, cambiar_programacion,
    ejecutar_turno, ejecutor_disponible, proximo_turno, turnos)


@override_settings(BACKUP_WORKER_ID="cesfam-tests")
class ProgramacionRespaldosTests(TestCase):
    def setUp(self):
        usuarios = get_user_model()
        self.admin = usuarios.objects.create_user(email="programador@example.com", is_superuser=True)
        self.otro = usuarios.objects.create_user(email="custodio-ejecutor@example.com")
        self.ahora = datetime(2026, 10, 25, 5, 0, tzinfo=utc.utc)  # 02:00 en Santiago.
        self.politica = PoliticaRespaldos.objects.create(pk=1, revision=1, frecuencia="DIARIA", hora=time(2),
            copias_diarias=7, copias_semanales=4, copias_mensuales=3, prueba_cada_dias=30,
            custodio=self.admin, suplente=self.otro, procedimiento_clave="Bóveda institucional.", ubicacion="OTRA")
        self.programacion = ProgramacionRespaldos.objects.create(pk=1, ejecutor="cesfam-tests", listo=True,
            ultimo_latido=self.ahora, politica_revision=1)
        self.copia = RespaldoBase.objects.create(motor="mariadb", version_origen="11.4", tamano=100, sha256="a" * 64)
        self.clave = patch("core.respaldo_programacion.leer_clave", return_value=b"x" * 32)
        self.clave.start(); self.addCleanup(self.clave.stop)
        self.cliente = patch("core.respaldo_programacion.shutil.which", return_value="/usr/bin/mariadb-dump")
        self.cliente.start(); self.addCleanup(self.cliente.stop)

    def activar(self):
        self.programacion.activa = True
        self.programacion.activada_at = self.ahora - timedelta(minutes=10)
        self.programacion.save()

    def test_horarios_diarios_semanales_y_cada_doce_horas(self):
        self.assertEqual(proximo_turno(self.politica, self.ahora), self.ahora + timedelta(days=1))
        self.politica.frecuencia = "DOCE_HORAS"
        self.assertEqual(proximo_turno(self.politica, self.ahora), self.ahora + timedelta(hours=12))
        self.politica.hora = time(20)
        local = [t.astimezone(CHILE) for t in turnos(self.politica, self.ahora) if t.astimezone(CHILE).date() == self.ahora.astimezone(CHILE).date()]
        self.assertEqual([t.hour for t in local], [8, 20])
        self.politica.frecuencia = "SEMANAL"
        self.politica.hora = time(2)
        self.politica.dia_semana = 0
        self.assertEqual(proximo_turno(self.politica, self.ahora).astimezone(CHILE).weekday(), 0)
        self.politica.frecuencia = "MANUAL"
        self.assertIsNone(proximo_turno(self.politica, self.ahora))

    def test_cambio_de_hora_hora_inexistente_y_hora_repetida(self):
        self.politica.hora = time(0, 30)
        referencia = datetime(2026, 9, 6, 12, tzinfo=utc.utc)
        horario = [t.astimezone(CHILE) for t in turnos(self.politica, referencia) if t.astimezone(CHILE).date() == referencia.date()]
        self.assertEqual(len(horario), 1)
        self.assertEqual((horario[0].hour, horario[0].minute), (1, 0))
        self.politica.hora = time(23, 30)
        referencia = datetime(2026, 4, 4, 12, tzinfo=utc.utc)
        horario = [t.astimezone(CHILE) for t in turnos(self.politica, referencia) if t.astimezone(CHILE).date() == referencia.date()]
        self.assertEqual(len(horario), 1)
        self.assertEqual(horario[0].fold, 0)

    def test_activacion_registra_solicitud_aunque_el_ejecutor_pierda_senal(self):
        with patch("core.respaldo_programacion.timezone.now", return_value=self.ahora):
            cambiar_programacion(usuario=self.admin, activar=True, revision=0, politica_revision=1, motivo="Inicio institucional")
        self.programacion.refresh_from_db()
        self.assertTrue(self.programacion.activa)
        self.assertEqual(CambioProgramacionRespaldos.objects.get().realizado_por, self.admin)
        with self.assertRaises(ValidationError):
            cambiar_programacion(usuario=self.admin, activar=False, revision=0, politica_revision=1, motivo="Pestaña antigua")
        cambiar_programacion(usuario=self.admin, activar=False, revision=1, politica_revision=1, motivo="Mantenimiento")
        self.programacion.refresh_from_db()
        self.assertFalse(self.programacion.activa)
        self.assertFalse(ejecutor_disponible(self.programacion, self.ahora + timedelta(minutes=4)))
        with patch("core.respaldo_programacion.timezone.now", return_value=self.ahora + timedelta(minutes=4)):
            cambiar_programacion(usuario=self.admin, activar=True, revision=2, politica_revision=1, motivo="Sin ejecutor")
        self.programacion.refresh_from_db()
        self.assertTrue(self.programacion.activa)
        self.assertFalse(ejecutor_disponible(self.programacion, self.ahora + timedelta(minutes=4)))

    def test_no_activa_politica_parcial_ni_revision_antigua(self):
        self.politica.suplente = None; self.politica.save()
        with patch("core.respaldo_programacion.timezone.now", return_value=self.ahora), self.assertRaises(ValidationError):
            cambiar_programacion(usuario=self.admin, activar=True, revision=0, politica_revision=1, motivo="Falta suplente")
        with self.assertRaises(ValidationError):
            cambiar_programacion(usuario=self.admin, activar=True, revision=0, politica_revision=0, motivo="Desactualizada")
        self.assertFalse(CambioProgramacionRespaldos.objects.exists())

    def test_ejecuta_una_vez_por_turno_y_no_acumula_copias_perdidas(self):
        self.activar()
        with patch("core.respaldo_programacion.crear_respaldo", return_value=self.copia) as crear:
            self.assertEqual(ejecutar_turno(ahora=self.ahora), "Copia creada")
            ejecutar_turno(ahora=self.ahora + timedelta(minutes=1))
            self.assertEqual(crear.call_count, 1)
            ejecutar_turno(ahora=self.ahora + timedelta(days=4))
            self.assertEqual(crear.call_count, 2)
        self.assertEqual(EjecucionProgramadaRespaldo.objects.count(), 2)
        self.assertEqual(EjecucionProgramadaRespaldo.objects.first().programada_para, self.ahora + timedelta(days=4))
        self.assertEqual(EjecucionProgramadaRespaldo.objects.first().respaldo, self.copia)

    def test_suspendida_sin_clave_y_otro_ejecutor_no_generan_copias(self):
        with patch("core.respaldo_programacion.crear_respaldo") as crear:
            ejecutar_turno(ahora=self.ahora)
            self.activar()
            with patch("core.respaldo_programacion.leer_clave", side_effect=ErrorRespaldo("Clave no disponible")):
                ejecutar_turno(ahora=self.ahora)
            self.programacion.refresh_from_db()
            self.assertFalse(self.programacion.listo)
            self.assertFalse(EjecucionProgramadaRespaldo.objects.exists())
            with override_settings(BACKUP_WORKER_ID="otro-equipo"), self.assertRaises(ErrorRespaldo):
                ejecutar_turno(ahora=self.ahora)
            crear.assert_not_called()

    def test_turnos_anteriores_a_activacion_no_se_ejecutan(self):
        self.activar()
        self.programacion.activada_at = self.ahora + timedelta(seconds=1)
        self.programacion.save()
        with patch("core.respaldo_programacion.crear_respaldo") as crear:
            ejecutar_turno(ahora=self.ahora + timedelta(minutes=1))
            crear.assert_not_called()

    def test_custodio_inactivo_impide_ejecutar_y_actualiza_diagnostico(self):
        self.activar()
        self.otro.is_active = False
        self.otro.save(update_fields=["is_active"])
        with patch("core.respaldo_programacion.crear_respaldo") as crear:
            ejecutar_turno(ahora=self.ahora)
            crear.assert_not_called()
        self.programacion.refresh_from_db()
        self.assertFalse(self.programacion.listo)
        self.assertIn("política vigente requiere revisión", self.programacion.diagnostico)

    def test_fallo_registrado_sin_exponer_excepciones_ni_reintentar(self):
        self.activar()
        with patch("core.respaldo_programacion.crear_respaldo", side_effect=RuntimeError("password=NO_PUBLICAR")) as crear:
            self.assertEqual(ejecutar_turno(ahora=self.ahora), "Fallida")
            ejecutar_turno(ahora=self.ahora + timedelta(minutes=1))
            self.assertEqual(crear.call_count, 1)
        ejecucion = EjecucionProgramadaRespaldo.objects.get()
        self.assertEqual(ejecucion.estado, "FALLIDA")
        self.assertNotIn("NO_PUBLICAR", ejecucion.detalle)
        self.assertIsNone(ejecucion.respaldo)

    def test_bloqueo_exclusivo_e_interrupcion_no_se_presenta_como_exito(self):
        self.activar()
        with bloqueo_programador() as adquirido:
            self.assertTrue(adquirido)
            with patch("core.respaldo_programacion.crear_respaldo") as crear:
                self.assertIn("Otro proceso", ejecutar_turno(ahora=self.ahora))
                crear.assert_not_called()
        ejecucion = EjecucionProgramadaRespaldo.objects.create(ejecutor="cesfam-tests", politica_revision=1, programada_para=self.ahora)
        with patch("core.respaldo_programacion.crear_respaldo") as crear:
            ejecutar_turno(ahora=self.ahora)
            crear.assert_not_called()
        ejecucion.refresh_from_db()
        self.assertEqual(ejecucion.estado, "INTERRUMPIDA")

    def test_cambiar_politica_suspende_y_deja_historial(self):
        self.activar()
        datos = {"revision": 1, "frecuencia": "DIARIA", "hora": "03:00", "dia_semana": "", "copias_diarias": 7,
            "copias_semanales": 4, "copias_mensuales": 3, "prueba_cada_dias": 30, "custodio": self.admin.pk,
            "suplente": self.otro.pk, "procedimiento_clave": "Bóveda", "ubicacion": "OTRA",
            "proteccion_adicional": "", "motivo": "Nuevo horario"}
        form = PoliticaRespaldosForm(datos, instance=self.politica)
        self.assertTrue(form.is_valid(), form.errors)
        guardar_politica(usuario=self.admin, datos=form.cleaned_data)
        self.programacion.refresh_from_db()
        self.assertFalse(self.programacion.activa)
        self.assertFalse(CambioProgramacionRespaldos.objects.get().activa)

    def test_permisos_csrf_y_confirmacion_en_panel(self):
        url = reverse("configurar_programacion_respaldos")
        datos = {"accion": "activar", "revision": 0, "politica_revision": 1, "motivo": "Activar", "confirmar": "on"}
        self.client.force_login(self.otro)
        self.assertEqual(self.client.post(url, datos).status_code, 403)
        cliente = Client(enforce_csrf_checks=True); cliente.force_login(self.admin)
        self.assertEqual(cliente.post(url, datos).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch("core.respaldo_programacion.timezone.now", return_value=self.ahora):
            self.client.force_login(self.admin)
            response = self.client.post(url, {**datos, "confirmar": ""})
            self.assertContains(response, "No se cambió la programación")
            self.assertEqual(response.context["form_programacion"]["motivo"].value(), "Activar")
            self.assertFalse(CambioProgramacionRespaldos.objects.exists())
            response = self.client.post(url, datos, follow=True)
            self.assertTrue(CambioProgramacionRespaldos.objects.exists(), [str(m) for m in response.context["messages"]])
        self.assertTrue(CambioProgramacionRespaldos.objects.get().activa)

    @override_settings(BACKUP_WORKER_ID="")
    def test_solicitud_sin_ejecutor_no_se_muestra_como_operativa(self):
        self.programacion.delete()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("configurar_programacion_respaldos"), {
            "accion": "activar", "revision": 0, "politica_revision": 1, "motivo": "Preparar horario", "confirmar": "on"}, follow=True)
        self.assertContains(response, "Solicitada · Pendiente del servidor")
        self.assertNotContains(response, "Activa · Ejecutor disponible")
        self.assertTrue(ProgramacionRespaldos.objects.get().activa)
        self.assertFalse(EjecucionProgramadaRespaldo.objects.exists())

    def test_manual_informa_bloqueo_en_el_mismo_formulario(self):
        self.politica.frecuencia = "MANUAL"
        self.politica.save()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("configurar_programacion_respaldos"), {
            "accion": "activar", "revision": 0, "politica_revision": 1, "motivo": "Mi motivo", "confirmar": "on"})
        self.assertContains(response, "La frecuencia está en Manual o Sin definir")
        self.assertEqual(response.context["form_programacion"]["motivo"].value(), "Mi motivo")
        self.assertFalse(CambioProgramacionRespaldos.objects.exists())

    def test_bloqueo_mysql_se_libera_incluso_ante_error(self):
        with patch("core.respaldo_programacion.connection") as base:
            base.vendor = "mysql"; base.settings_dict = {"NAME": "prueba"}
            cursor = base.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            with self.assertRaises(RuntimeError):
                with bloqueo_programador() as adquirido:
                    self.assertTrue(adquirido)
                    raise RuntimeError("Fin inesperado")
            self.assertEqual(cursor.execute.call_count, 2)
            self.assertIn("RELEASE_LOCK", cursor.execute.call_args.args[0])

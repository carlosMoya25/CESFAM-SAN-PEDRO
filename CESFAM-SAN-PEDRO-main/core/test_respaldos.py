import io
import json
import os
import tempfile
import zipfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DescargaRespaldo, PruebaRestauracion, RespaldoBase
from .respaldo_crypto import (ErrorRespaldo, cifrar, descifrar, guardar_manifiesto, leer_clave,
                             leer_manifiesto, rutas)
from .respaldos import argumentos_dump, crear_respaldo, probar_restauracion


class ProcesoDump:
    def __init__(self, sql, retorno=0):
        self.stdout = io.BytesIO(sql)
        self.retorno = retorno

    def wait(self, **kwargs):
        return self.retorno

    def poll(self):
        return self.retorno

    def kill(self):
        pass


class RespaldosTests(TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.root = Path(self.temporal.name) / "copias"
        self.clave = Path(self.temporal.name) / "claves" / "backup.key"
        self.override = override_settings(BACKUP_ROOT=self.root, BACKUP_KEY_FILE=self.clave)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def copia(self, sql=None, retorno=0):
        sql = sql if sql is not None else b"CREATE TABLE `tabla` (id integer);\nINSERT INTO `tabla` VALUES (1);\n"
        origen = {"base": "base_prueba", "motor": "mariadb", "version": "11.4.5-MariaDB", "imagen": "mariadb:11.4", "filas": {"tabla": 0}}
        with patch("core.respaldos.metadatos_origen", return_value=origen), patch("core.respaldos.shutil.which", return_value="/usr/bin/mysqldump"), patch("core.respaldos.subprocess.Popen", return_value=ProcesoDump(sql, retorno)):
            return crear_respaldo(crear_clave=True)

    def test_cifrado_autenticado_y_clave_no_se_reemplaza(self):
        clave = leer_clave(crear=True)
        self.assertEqual(leer_clave(crear=True), clave)
        self.assertEqual(self.clave.stat().st_mode & 0o777, 0o600)
        with tempfile.TemporaryFile() as archivo:
            cifrar([b"contenido privado", b" y completo"], archivo, clave)
            archivo.seek(0)
            self.assertNotIn(b"contenido privado", archivo.read())
            archivo.seek(0)
            destino = io.BytesIO()
            descifrar(archivo, destino, clave)
            self.assertEqual(destino.getvalue(), b"contenido privado y completo")
            archivo.seek(0)
            with self.assertRaises(ErrorRespaldo):
                descifrar(archivo, io.BytesIO(), os.urandom(32))

    def test_manifiesto_alterado_rechazado(self):
        clave = leer_clave(crear=True)
        path = self.root / "test.json"
        guardar_manifiesto(path, {"dato": 1}, clave)
        self.assertEqual(leer_manifiesto(path, clave), {"dato": 1})
        datos = json.loads(path.read_text())
        datos["datos"]["dato"] = 2
        path.write_text(json.dumps(datos))
        with self.assertRaises(ErrorRespaldo):
            leer_manifiesto(path, clave)

    def test_almacenamiento_publico_y_permisos_inseguros_rechazados(self):
        with override_settings(BACKUP_ROOT=Path(__file__).resolve().parent.parent / "static" / "copias"):
            with self.assertRaises(ErrorRespaldo):
                rutas()
        with override_settings(BACKUP_KEY_FILE=self.root / "clave"):
            with self.assertRaises(ErrorRespaldo):
                rutas()
        leer_clave(crear=True)
        self.clave.chmod(0o644)
        with self.assertRaises(ErrorRespaldo):
            leer_clave()

    def test_copia_en_stream_sin_sql_o_credenciales_persistentes(self):
        copia = self.copia()
        self.assertEqual(copia.verificacion, {})
        self.assertIsNone(copia.verificado_at)
        archivos = list(self.root.iterdir())
        self.assertEqual(len(archivos), 2)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in archivos))
        self.assertNotIn(b"INSERT INTO", (self.root / f"{copia.pk.hex}.cesfam").read_bytes())
        meta = leer_manifiesto(self.root / f"{copia.pk.hex}.json", leer_clave())
        self.assertEqual(meta["filas"], {"tabla": 1})

    def test_fallo_o_volcado_incompleto_no_deja_copia_parcial(self):
        for sql, retorno in ((b"", 1), (b"", 0), (b"INSERT INTO `otra` VALUES(1);\n", 0)):
            with self.assertRaises(ErrorRespaldo):
                self.copia(sql=sql, retorno=retorno)
        self.assertFalse(RespaldoBase.objects.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_tls_obligatorio_y_secretos_fuera_de_argumentos(self):
        args = argumentos_dump("/usr/bin/mysqldump", "/tmp/client.cnf", "base")
        self.assertIn("--ssl-mode=REQUIRED", args)
        self.assertIn("--skip-extended-insert", args)
        self.assertNotIn("--databases", args)
        self.assertFalse(any("password" in a for a in args))
        self.assertIn("--ssl-verify-server-cert", argumentos_dump("/usr/bin/mariadb-dump", "/tmp/c.cnf", "base"))

    def docker_correcto(self, args, **kwargs):
        if "UNION ALL" in str(args) or any("COUNT(*)" in a for a in args):
            return "tabla\t1"
        return "1"

    def test_prueba_se_aisla_y_registra_importacion_y_recuentos(self):
        copia = self.copia()
        with patch("core.respaldos.docker", side_effect=self.docker_correcto) as motor:
            resultado = probar_restauracion(copia.pk)
        self.assertEqual(resultado["estado"], "OK")
        run = next(c.args[0] for c in motor.call_args_list if c.args[0][0] == "run")
        self.assertIn("--network=none", run)
        self.assertIn("--pull=never", run)
        self.assertNotIn("--publish", run)
        self.assertTrue(any(c.args[0][:3] == ["rm", "--force", "--volumes"] for c in motor.call_args_list))
        copia.refresh_from_db()
        self.assertIsNotNone(copia.verificado_at)
        self.assertTrue(PruebaRestauracion.objects.get().correcta)
        self.assertFalse(any(p.is_dir() for p in self.root.iterdir()))

    def test_recuentos_incorrectos_no_marcan_copia_verificada(self):
        copia = self.copia()
        def motor(args, **kwargs):
            return "tabla\t9" if any("COUNT(*)" in a for a in args) else "1"
        with patch("core.respaldos.docker", side_effect=motor), self.assertRaises(ErrorRespaldo):
            probar_restauracion(copia.pk)
        copia.refresh_from_db()
        self.assertIsNone(copia.verificado_at)
        self.assertFalse(PruebaRestauracion.objects.get().correcta)

    def test_cliente_docker_solo_monta_credenciales_temporales_y_exige_tls(self):
        origen = {"base": "base_prueba", "motor": "mariadb", "version": "11.4.5-MariaDB", "imagen": "mariadb:11.4", "filas": {"tabla": 0}}
        proceso = ProcesoDump(b"CREATE TABLE `tabla` (id integer);\nINSERT INTO `tabla` VALUES (1);\n")
        with patch("core.respaldos.metadatos_origen", return_value=origen), patch("core.respaldos.docker", return_value="OK"), patch("core.respaldos.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"")), patch("core.respaldos.subprocess.Popen", return_value=proceso) as abrir:
            crear_respaldo(crear_clave=True, cliente_docker=True)
        args = abrir.call_args.args[0]
        self.assertEqual(args[:2], ["docker", "run"])
        self.assertIn("--ssl-verify-server-cert", args)
        self.assertIn("--pull=never", args)
        montaje = args[args.index("--mount") + 1]
        self.assertIn(".backup_", montaje)
        self.assertIn("readonly", montaje)
        self.assertNotIn(str(self.clave), montaje)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_no_declara_exito_si_no_se_retira_el_contenedor_de_restauracion(self):
        copia = self.copia()
        def motor(args, **kwargs):
            if args[0] == "rm":
                raise ErrorRespaldo("Retiro no disponible")
            return self.docker_correcto(args, **kwargs)
        with patch("core.respaldos.docker", side_effect=motor), self.assertRaises(ErrorRespaldo):
            probar_restauracion(copia.pk)
        copia.refresh_from_db()
        self.assertIsNone(copia.verificado_at)
        self.assertTrue(copia.verificacion["contenedor_pendiente"].startswith("cesfam_restore_"))
        self.assertFalse(PruebaRestauracion.objects.get().correcta)

    def test_copia_alterada_no_se_importa_y_registra_fallo(self):
        copia = self.copia()
        path = self.root / f"{copia.pk.hex}.cesfam"
        path.write_bytes(path.read_bytes()[:-1] + b"X")
        with patch("core.respaldos.docker") as motor, self.assertRaises(ErrorRespaldo):
            probar_restauracion(copia.pk)
        motor.assert_not_called()
        self.assertFalse(PruebaRestauracion.objects.get().correcta)

    def test_panel_solo_administradores_no_expone_archivos_ni_clave(self):
        copia = self.copia()
        usuario = get_user_model().objects.create_user(email="usuario-respaldo@example.com")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("panel_respaldos")).status_code, 403)
        usuario.groups.add(Group.objects.get_or_create(name="Administrador")[0])
        response = self.client.get(reverse("panel_respaldos"))
        self.assertContains(response, "Restauración pendiente")
        self.assertNotContains(response, str(self.clave))
        self.assertNotContains(response, ".cesfam")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(self.client.post(reverse("panel_respaldos")), "No se guardaron los cambios")

    def test_descarga_cifrada_con_manifiesto_y_historial_para_tecnico(self):
        copia = self.copia()
        tecnico = get_user_model().objects.create_user(email="tecnico-backup@example.com")
        tecnico.groups.add(Group.objects.get_or_create(name="Técnico TI")[0])
        self.client.force_login(tecnico)
        self.assertEqual(self.client.get(reverse("panel_respaldos")).status_code, 200)
        url = reverse("descargar_respaldo", args=[copia.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        contenido = b"".join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(io.BytesIO(contenido)) as paquete:
            self.assertEqual(set(paquete.namelist()), {f"{copia.pk.hex}.cesfam", f"{copia.pk.hex}.json"})
            self.assertEqual(paquete.read(f"{copia.pk.hex}.cesfam"), (self.root / f"{copia.pk.hex}.cesfam").read_bytes())
            self.assertEqual(paquete.read(f"{copia.pk.hex}.json"), (self.root / f"{copia.pk.hex}.json").read_bytes())
            self.assertNotIn(b"CREATE TABLE", paquete.read(f"{copia.pk.hex}.cesfam"))
        registro = DescargaRespaldo.objects.get()
        self.assertEqual(registro.usuario, tecnico)
        self.assertEqual(registro.sha256, copia.sha256)
        historial = self.client.get(reverse("historial_descargas_respaldos"))
        self.assertContains(historial, tecnico.email)
        self.assertIn("no-store", historial["Cache-Control"])

    def test_usuario_comun_no_puede_descargar_ni_ver_historial(self):
        copia = self.copia()
        usuario = get_user_model().objects.create_user(email="sin-acceso@example.com")
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(reverse("descargar_respaldo", args=[copia.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("historial_descargas_respaldos")).status_code, 403)
        self.assertFalse(DescargaRespaldo.objects.exists())

    def test_descarga_requiere_csrf(self):
        from django.test import Client
        copia = self.copia()
        admin = get_user_model().objects.create_user(email="admin-csrf@example.com", is_superuser=True)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(admin)
        self.assertEqual(cliente.post(reverse("descargar_respaldo", args=[copia.pk])).status_code, 403)
        self.assertFalse(DescargaRespaldo.objects.exists())

    def test_panel_destaca_ultima_copia_y_pagina_anteriores_sin_repetirla(self):
        admin = get_user_model().objects.create_user(email="admin-panel@example.com", is_superuser=True)
        self.client.force_login(admin)
        for _ in range(12):
            RespaldoBase.objects.create(motor="mariadb", version_origen="11.4", tamano=100, sha256="a" * 64)
        ultima = RespaldoBase.objects.order_by("-creado_at", "-pk").first()
        response = self.client.get(reverse("panel_respaldos"))
        self.assertEqual(response.context["ultima"].pk, ultima.pk)
        self.assertEqual(len(response.context["copias"]), 10)
        self.assertNotIn(ultima.pk, [c.pk for c in response.context["copias"]])
        self.assertContains(response, "Archivo no disponible en este servidor")
        self.assertNotContains(response, "Recuperación comprobada ·")
        pagina2 = self.client.get(reverse("panel_respaldos"), {"pagina": 2})
        self.assertEqual(pagina2.context["ultima"].pk, ultima.pk)
        self.assertEqual(len(pagina2.context["copias"]), 1)

    def test_copia_alterada_ausente_o_enlazada_no_se_descarga(self):
        copia = self.copia()
        admin = get_user_model().objects.create_user(email="admin-descarga@example.com", is_superuser=True)
        self.client.force_login(admin)
        url = reverse("descargar_respaldo", args=[copia.pk])
        path = self.root / f"{copia.pk.hex}.cesfam"
        path.write_bytes(b"alterado")
        self.assertEqual(self.client.post(url).status_code, 409)
        path.unlink()
        self.assertEqual(self.client.post(url).status_code, 409)
        path.symlink_to(self.clave)
        self.assertEqual(self.client.post(url).status_code, 409)
        self.assertFalse(DescargaRespaldo.objects.exists())

import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from django.db import connection, transaction
from django.utils import timezone

from .models import PruebaRestauracion, RespaldoBase
from .respaldo_crypto import (ErrorRespaldo, archivo_privado, cifrar, descifrar, guardar_manifiesto,
                             leer_clave, leer_manifiesto, rutas, sha256_archivo)


IDENTIFICADOR = re.compile(r"^[A-Za-z0-9_]{1,64}$")
INSERT = re.compile(rb"^INSERT INTO `([A-Za-z0-9_]+)` ")
CREATE = re.compile(rb"^CREATE TABLE `([A-Za-z0-9_]+)` ")


def opcion(valor):
    return '"' + str(valor).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


def metadatos_origen():
    if connection.vendor != "mysql":
        raise ErrorRespaldo("La copia SQL requiere MySQL o MariaDB.")
    base = connection.settings_dict["NAME"]
    if not IDENTIFICADOR.fullmatch(base):
        raise ErrorRespaldo("Nombre de base no admitido para esta herramienta.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'", [base])
        tablas = dict(cursor.fetchall())
    if not tablas or any(motor != "InnoDB" or not IDENTIFICADOR.fullmatch(nombre) for nombre, motor in tablas.items()):
        raise ErrorRespaldo("Se requiere una base con tablas InnoDB y nombres compatibles para la copia transaccional.")
    familia = "mariadb" if "mariadb" in version.lower() else "mysql"
    coincidencia = re.match(r"(\d+\.\d+)", version)
    if not coincidencia:
        raise ErrorRespaldo("No se pudo identificar la versión del servidor.")
    return {"base": base, "motor": familia, "version": version, "imagen": f"{familia}:{coincidencia.group(1)}",
            "filas": {nombre: 0 for nombre in tablas}}


def argumentos_dump(ejecutable, credenciales, base):
    maria = "mariadb" in Path(ejecutable).name
    args = [ejecutable, f"--defaults-extra-file={credenciales}", "--protocol=TCP", "--single-transaction", "--quick",
            "--skip-lock-tables", "--skip-add-locks", "--skip-extended-insert", "--hex-blob", "--routines", "--events",
            "--triggers", "--default-character-set=utf8mb4"]
    args += ["--ssl", "--ssl-verify-server-cert"] if maria else ["--ssl-mode=REQUIRED", "--no-tablespaces", "--column-statistics=0", "--set-gtid-purged=OFF"]
    return args + [base]


def crear_respaldo(*, crear_clave=False, cliente_docker=False):
    root, _ = rutas()
    clave = leer_clave(crear=crear_clave)
    ejecutable = shutil.which("mariadb-dump") or shutil.which("mysqldump")
    if not ejecutable and not cliente_docker:
        raise ErrorRespaldo("Instala el cliente oficial MariaDB/MySQL de respaldo en el servidor.")
    meta = metadatos_origen()
    if cliente_docker:
        docker(["info", "--format", "{{.ServerVersion}}"])
        docker(["image", "inspect", meta["imagen"]])
    identificador = uuid.uuid4()
    copia = root / f"{identificador.hex}.cesfam"
    manifiesto = root / f"{identificador.hex}.json"
    cliente_nombre = f"cesfam_dump_{uuid.uuid4().hex}"
    conf = connection.settings_dict
    try:
        with tempfile.TemporaryDirectory(prefix=".backup_", dir=root) as temporal:
            credenciales = Path(temporal) / "client.cnf"
            opciones = {"host": conf.get("HOST") or "127.0.0.1", "port": conf.get("PORT") or "3306",
                        "user": conf["USER"], "password": conf["PASSWORD"]}
            for campo in ("ca", "cert", "key"):
                valor = conf.get("OPTIONS", {}).get("ssl", {}).get(campo)
                if valor:
                    if cliente_docker:
                        destino = Path(temporal) / f"ssl-{campo}.pem"
                        with archivo_privado(destino) as archivo:
                            archivo.write(Path(valor).read_bytes())
                        valor = f"/run/backup/ssl-{campo}.pem"
                    opciones[f"ssl-{campo}"] = valor
            with archivo_privado(credenciales) as archivo:
                archivo.write(("[client]\n" + "\n".join(f"{campo}={opcion(valor)}" for campo, valor in opciones.items()) + "\n").encode())
            with tempfile.TemporaryFile() as errores:
                argumentos = argumentos_dump(ejecutable, credenciales, meta["base"]) if not cliente_docker else [
                    "docker", "run", "--rm", "--pull=never", "--name", cliente_nombre,
                    "--label", "cesfam.backup-client=true", "--memory=512m", "--cpus=1",
                    "--mount", f"type=bind,src={temporal},dst=/run/backup,readonly",
                    "--tmpfs", "/var/lib/mysql:rw,size=16m", "--entrypoint=mariadb-dump" if meta["motor"] == "mariadb" else "--entrypoint=mysqldump",
                    meta["imagen"], *argumentos_dump("mariadb-dump" if meta["motor"] == "mariadb" else "mysqldump", "/run/backup/client.cnf", meta["base"])[1:]]
                proceso = subprocess.Popen(argumentos,
                                           stdout=subprocess.PIPE, stderr=errores)
                reloj = threading.Timer(900, proceso.kill)
                reloj.start()
                try:
                    estructuras = set()
                    def lineas():
                        for linea in proceso.stdout:
                            estructura = CREATE.match(linea)
                            if estructura and estructura.group(1).decode() in meta["filas"]:
                                estructuras.add(estructura.group(1).decode())
                            if linea.startswith(b"INSERT INTO"):
                                match = INSERT.match(linea)
                                if not match or match.group(1).decode() not in meta["filas"]:
                                    raise ErrorRespaldo("El volcado contiene una tabla o formato de inserción inesperado.")
                                meta["filas"][match.group(1).decode()] += 1
                            yield linea
                    with archivo_privado(copia) as archivo:
                        cifrar(lineas(), archivo, clave)
                    if proceso.wait(timeout=10) != 0:
                        errores.seek(0)
                        mensaje = errores.read(8192).upper()
                        if b"SSL" in mensaje or b"TLS" in mensaje:
                            raise ErrorRespaldo("El cliente no pudo establecer la conexión TLS requerida para la copia.")
                        if b"AUTHENTICATION PLUGIN" in mensaje or b"CANNOT BE LOADED" in mensaje:
                            raise ErrorRespaldo("El cliente local no admite la autenticación del servidor. Usa --cliente-docker con su imagen oficial compatible.")
                        raise ErrorRespaldo("El cliente no completó el volcado. Revisa conectividad, compatibilidad y permisos de respaldo; no se conserva una copia parcial.")
                    if estructuras != set(meta["filas"]):
                        raise ErrorRespaldo("El volcado no incluye la estructura de todas las tablas esperadas.")
                finally:
                    reloj.cancel()
                    if proceso.poll() is None:
                        proceso.kill()
                    proceso.wait()
                    proceso.stdout.close()
                    if cliente_docker:
                        estado = subprocess.run(["docker", "ps", "--all", "--quiet", "--filter", f"name=^{cliente_nombre}$",
                                                 "--filter", "label=cesfam.backup-client=true"], stdout=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL, timeout=30)
                        if estado.returncode:
                            raise ErrorRespaldo(f"No se pudo confirmar el retiro del cliente temporal {cliente_nombre}.")
                        if estado.stdout.strip():
                            docker(["rm", "--force", "--volumes", cliente_nombre])
        meta.update({"id": str(identificador), "formato": 1, "fecha": timezone.now().isoformat(),
                     "sha256": sha256_archivo(copia), "tamano": copia.stat().st_size})
        guardar_manifiesto(manifiesto, meta, clave)
        with transaction.atomic():
            return RespaldoBase.objects.create(id=identificador, motor=meta["motor"], version_origen=meta["version"][:120],
                                               tamano=meta["tamano"], sha256=meta["sha256"])
    except BaseException:
        copia.unlink(missing_ok=True)
        manifiesto.unlink(missing_ok=True)
        raise


def cargar_copia(identificador):
    identificador = uuid.UUID(str(identificador))
    root, _ = rutas()
    clave = leer_clave()
    copia = root / f"{identificador.hex}.cesfam"
    meta = leer_manifiesto(root / f"{identificador.hex}.json", clave)
    if (meta.get("formato") != 1 or meta.get("id") != str(identificador) or copia.is_symlink()
            or not copia.is_file() or sha256_archivo(copia) != meta.get("sha256")):
        raise ErrorRespaldo("La copia no está disponible o su integridad no coincide con el manifiesto firmado.")
    if (not IDENTIFICADOR.fullmatch(meta.get("base", "")) or not meta.get("filas")
            or any(not IDENTIFICADOR.fullmatch(t) or not isinstance(n, int) or n < 0 for t, n in meta["filas"].items())
            or not re.fullmatch(r"(?:mysql|mariadb):\d+\.\d+", meta.get("imagen", ""))):
        raise ErrorRespaldo("El manifiesto no contiene un destino de prueba compatible.")
    return copia, meta, clave


def docker(args, *, env=None, entrada=None, timeout=30):
    try:
        resultado = subprocess.run(["docker", *args], stdin=entrada, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ErrorRespaldo("Docker no está disponible o la operación de prueba agotó su tiempo.") from None
    if resultado.returncode:
        raise ErrorRespaldo("La operación aislada de Docker no se completó. Comprueba Docker Desktop y la imagen local indicada en el manifiesto.")
    return resultado.stdout.decode("utf-8", errors="replace").strip()


def probar_restauracion(identificador):
    nombre = f"cesfam_restore_{uuid.uuid4().hex}"
    registro = RespaldoBase.objects.filter(pk=identificador).first()
    detalle = {"red": "none", "puertos_publicados": False}
    creado = False
    try:
        copia, meta, clave = cargar_copia(identificador)
        root, _ = rutas()
        detalle["imagen"] = meta["imagen"]
        docker(["info", "--format", "{{.ServerVersion}}"])
        docker(["image", "inspect", meta["imagen"]])  # No descargar ni ejecutar imágenes arbitrarias.
        with tempfile.TemporaryDirectory(prefix=".restore_", dir=root) as temporal:
            sql = Path(temporal) / "copia.sql"
            with open(copia, "rb") as origen, archivo_privado(sql) as destino:
                descifrar(origen, destino, clave)
            password = secrets.token_urlsafe(32)
            entorno = os.environ.copy()
            entorno["MYSQL_PWD"] = password
            archivo_env = Path(temporal) / "container.env"
            with archivo_privado(archivo_env) as archivo:
                archivo.write(f"MYSQL_ROOT_PASSWORD={password}\n".encode())
            docker(["run", "--detach", "--pull=never", "--name", nombre, "--network=none", "--memory=2g", "--cpus=2",
                    "--tmpfs", "/var/lib/mysql:rw,size=1024m,mode=0700", "--env-file", str(archivo_env),
                    "--label", "cesfam.restore-test=true", meta["imagen"], "--event-scheduler=OFF"], timeout=60)
            creado = True
            cliente = "mariadb" if meta["motor"] == "mariadb" else "mysql"
            comando = ["exec", "--env", "MYSQL_PWD", nombre, cliente, "--protocol=socket", "--user=root", "--batch", "--skip-column-names"]
            for _ in range(90):
                try:
                    docker([*comando, "-e", "SELECT 1"], env=entorno, timeout=5)
                    break
                except ErrorRespaldo:
                    time.sleep(1)
            else:
                raise ErrorRespaldo("El servidor temporal no inició correctamente.")
            docker([*comando, "-e", f"CREATE DATABASE `{meta['base']}` CHARACTER SET utf8mb4"], env=entorno)
            with open(sql, "rb") as entrada:
                docker([*comando[:1], "--interactive", *comando[1:], "--binary-mode", f"--database={meta['base']}"],
                       env=entorno, entrada=entrada, timeout=600)
            consulta = " UNION ALL ".join(f"SELECT '{tabla}', COUNT(*) FROM `{meta['base']}`.`{tabla}`" for tabla in sorted(meta["filas"]))
            lineas = docker([*comando, "-e", consulta], env=entorno, timeout=120)
            observadas = dict((tabla, int(cantidad)) for tabla, cantidad in (linea.split("\t") for linea in lineas.splitlines()))
            if observadas != meta["filas"]:
                raise ErrorRespaldo("La importación terminó, pero no coinciden los recuentos de tablas y filas de la copia.")
            detalle.update({"estado": "OK", "tablas": len(observadas), "filas": sum(observadas.values())})
    except Exception as exc:
        detalle.update({"estado": "FALLIDA", "motivo": str(exc) if isinstance(exc, ErrorRespaldo) else "Error interno de verificación."})
    finally:
        if creado:
            try:
                docker(["rm", "--force", "--volumes", nombre])
                detalle["contenedor_retirado"] = True
            except ErrorRespaldo:
                detalle.update({"estado": "FALLIDA", "contenedor_pendiente": nombre, "motivo": "No se pudo retirar el contenedor temporal."})
        if registro:
            with transaction.atomic():
                PruebaRestauracion.objects.create(respaldo=registro, correcta=detalle.get("estado") == "OK", detalle=detalle)
                registro.verificacion = detalle
                if detalle.get("estado") == "OK":
                    registro.verificado_at = timezone.now()
                registro.save(update_fields=["verificacion", "verificado_at"])
    if detalle.get("estado") != "OK":
        raise ErrorRespaldo(detalle.get("motivo", "La prueba no se completó."))
    return detalle

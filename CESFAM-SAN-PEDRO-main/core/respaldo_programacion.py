"""Programación de copias SQL. No transfiere, restaura ni elimina archivos."""
import re
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from usuarios.utils import es_administrador, es_tecnico
from .models import (CambioProgramacionRespaldos, EjecucionProgramadaRespaldo,
                     PoliticaRespaldos, ProgramacionRespaldos)
from .respaldo_crypto import ErrorRespaldo, leer_clave
from .respaldo_politica import pendientes_politica
from .respaldos import crear_respaldo


CHILE = ZoneInfo("America/Santiago")
AUTO = {"DIARIA", "DOCE_HORAS", "SEMANAL"}
_bloqueo_pruebas = threading.Lock()


def identificador_ejecutor():
    valor = settings.BACKUP_WORKER_ID
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", valor):
        raise ErrorRespaldo("Configura BACKUP_WORKER_ID con un identificador exclusivo del servidor de respaldos.")
    return valor


def turnos(politica, referencia):
    if politica.frecuencia not in AUTO or not politica.hora:
        return []
    fecha = referencia.astimezone(CHILE).date()
    horas = [politica.hora]
    if politica.frecuencia == "DOCE_HORAS":
        horas.append(politica.hora.replace(hour=(politica.hora.hour + 12) % 24))
    resultado = set()
    for diferencia in range(-8, 9):
        dia = fecha + timedelta(days=diferencia)
        if politica.frecuencia == "SEMANAL" and dia.weekday() != politica.dia_semana:
            continue
        for hora in horas:
            local = datetime.combine(dia, hora)
            # En cambio de hora: desplazar una hora inexistente hasta el primer minuto válido.
            # Una hora repetida se ejecuta una sola vez, en su primera ocurrencia (fold=0).
            for _ in range(181):
                utc = local.replace(tzinfo=CHILE, fold=0).astimezone(dt_timezone.utc)
                if utc.astimezone(CHILE).replace(tzinfo=None) == local:
                    resultado.add(utc)
                    break
                local += timedelta(minutes=1)
    return sorted(resultado)


def proximo_turno(politica, ahora):
    return next((turno for turno in turnos(politica, ahora) if turno > ahora), None)


def ejecutor_disponible(programacion, ahora):
    return bool(programacion and programacion.listo and programacion.ultimo_latido
                and timedelta(0) <= ahora - programacion.ultimo_latido <= timedelta(minutes=3))


@transaction.atomic
def cambiar_programacion(*, usuario, activar, revision, politica_revision, motivo):
    if not (es_administrador(usuario) or es_tecnico(usuario)):
        raise PermissionDenied
    # Mismo orden de bloqueos que el guardado de la política.
    politica = PoliticaRespaldos.objects.select_for_update().select_related("custodio", "suplente").filter(pk=1).first()
    ProgramacionRespaldos.objects.get_or_create(pk=1)
    programacion = ProgramacionRespaldos.objects.select_for_update().get(pk=1)
    if programacion.revision != revision or (politica.revision if politica else 0) != politica_revision:
        raise ValidationError("La configuración cambió. Recarga la página antes de confirmar.")
    if not motivo.strip():
        raise ValidationError("Indica el motivo de este cambio.")
    ahora = timezone.now()
    if activar:
        if not politica or politica.frecuencia not in AUTO:
            raise ValidationError("La frecuencia está en Manual o Sin definir. En «Editar política de respaldos», selecciona Diariamente, Cada 12 horas o Semanalmente y guarda antes de activar.")
        pendientes = pendientes_politica(politica)
        if pendientes:
            raise ValidationError(["Completa la política antes de solicitar la activación.", *pendientes])
        if settings.BACKUP_WORKER_ID:
            try:
                identificador = identificador_ejecutor()
            except ErrorRespaldo as exc:
                raise ValidationError(str(exc)) from None
            if programacion.ejecutor and programacion.ejecutor != identificador:
                raise ValidationError("El ejecutor registrado corresponde a otro servidor. Mantenimiento debe revisar la configuración.")
    if programacion.activa == activar:
        raise ValidationError("La programación ya tiene ese estado. Recarga la página.")
    programacion.activa = activar
    programacion.revision += 1
    programacion.politica_revision = politica_revision
    programacion.activada_at = ahora if activar else None
    programacion.save()
    CambioProgramacionRespaldos.objects.create(realizado_por=usuario, activa=activar,
        politica_revision=politica_revision, motivo=motivo.strip())
    return programacion


@contextmanager
def bloqueo_programador():
    """Un solo ejecutor a la vez, incluso si hay varios procesos o servidores."""
    if connection.vendor == "mysql":
        # GET_LOCK vive en la conexión, no en una transacción. Se libera al salir o caer el proceso.
        # El nombre distingue bases alojadas en un mismo motor.
        import hashlib
        nombre = "cesfam.backup." + hashlib.sha256(connection.settings_dict["NAME"].encode()).hexdigest()[:40]
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", [nombre])
            adquirido = cursor.fetchone()[0] == 1
        try:
            yield adquirido
        finally:
            if adquirido:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [nombre])
    elif connection.vendor == "sqlite" and connection.settings_dict["NAME"].startswith("file:memorydb"):
        # Solo la base efímera del entorno de pruebas; no es un ejecutor de producción SQLite.
        adquirido = _bloqueo_pruebas.acquire(blocking=False)
        try:
            yield adquirido
        finally:
            if adquirido:
                _bloqueo_pruebas.release()
    else:
        raise ErrorRespaldo("El ejecutor requiere MySQL/MariaDB para coordinar los procesos de respaldo.")


def ejecutar_turno(*, cliente_docker=False, ahora=None):
    ahora = ahora or timezone.now()
    identificador = identificador_ejecutor()
    with bloqueo_programador() as adquirido:
        if not adquirido:
            return "Otro proceso de respaldos está trabajando."
        programacion, _ = ProgramacionRespaldos.objects.get_or_create(pk=1)
        if programacion.ejecutor and programacion.ejecutor != identificador:
            raise ErrorRespaldo("La base ya está vinculada a otro ejecutor. Revisa el identificador institucional antes de continuar.")
        diagnostico = "Ejecutor disponible."
        listo = True
        try:
            leer_clave()  # No inicializa ni reemplaza claves automáticamente.
            if not cliente_docker and not (shutil.which("mariadb-dump") or shutil.which("mysqldump")):
                raise ErrorRespaldo("Falta el cliente oficial de respaldo en el servidor.")
            if cliente_docker and not shutil.which("docker"):
                raise ErrorRespaldo("Docker no está disponible para el cliente de respaldo.")
        except (ErrorRespaldo, OSError) as exc:
            listo, diagnostico = False, str(exc) if isinstance(exc, ErrorRespaldo) else "No se puede acceder al almacenamiento privado de respaldos o claves."
        ProgramacionRespaldos.objects.filter(pk=1).update(ejecutor=identificador, ultimo_latido=ahora,
                                                         listo=listo, diagnostico=diagnostico)
        # Poseer el bloqueo exclusivo demuestra que una ejecución anterior ya no mantiene su conexión.
        with transaction.atomic():
            for interrumpida in EjecucionProgramadaRespaldo.objects.filter(estado="EN_CURSO"):
                interrumpida.estado = "INTERRUMPIDA"
                interrumpida.finalizada_at = ahora
                interrumpida.detalle = "El ejecutor anterior terminó sin registrar el resultado. Revisar archivos antes de utilizarlos."
                interrumpida.save(update_fields=["estado", "finalizada_at", "detalle"])
        if not listo:
            return diagnostico
        with transaction.atomic():
            politica = PoliticaRespaldos.objects.select_for_update().select_related("custodio", "suplente").filter(pk=1).first()
            programacion = ProgramacionRespaldos.objects.select_for_update().get(pk=1)
            if not programacion.activa:
                return "Programación suspendida."
            if (not politica or programacion.politica_revision != politica.revision or pendientes_politica(politica)
                    or politica.frecuencia not in AUTO or not programacion.activada_at):
                ProgramacionRespaldos.objects.filter(pk=1).update(listo=False,
                    diagnostico="La política vigente requiere revisión; no se generarán copias hasta resolver los pendientes.")
                return "La política requiere revisión; no se generaron copias."
            vencidos = [turno for turno in turnos(politica, ahora) if programacion.activada_at <= turno <= ahora]
            if not vencidos:
                return "Sin ejecuciones pendientes."
            # Tras una interrupción larga, recuperar solo el último turno, sin producir una ráfaga de copias.
            ejecucion, nueva = EjecucionProgramadaRespaldo.objects.get_or_create(
                politica_revision=politica.revision, programada_para=vencidos[-1], defaults={"ejecutor": identificador})
            if not nueva:
                return "El último turno ya fue procesado."
        try:
            copia = crear_respaldo(cliente_docker=cliente_docker)
        except Exception:
            # No almacenar ni mostrar excepciones de SQL/subprocesos: pueden contener datos de conexión.
            ejecucion.estado = "FALLIDA"
            ejecucion.detalle = "No se completó la copia. Mantenimiento debe revisar conectividad, cliente SQL, clave y espacio disponible. No se reintenta este turno automáticamente."
        else:
            ejecucion.estado = "CORRECTA"
            ejecucion.respaldo = copia
            ejecucion.detalle = "Copia SQL cifrada creada. Recuperación y traslado a Windows pendientes de comprobar."
        ejecucion.finalizada_at = timezone.now()
        with transaction.atomic():
            ejecucion.save()
        ProgramacionRespaldos.objects.filter(pk=1).update(ultimo_latido=timezone.now())
        return ejecucion.get_estado_display()

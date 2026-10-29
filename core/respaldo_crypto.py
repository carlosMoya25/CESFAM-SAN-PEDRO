"""Formato privado de copia SQL con cifrado autenticado y manifiesto firmado."""
import hashlib
import hmac
import json
import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings


MAGIC = b"CESFAMSQL1\n"


class ErrorRespaldo(Exception):
    pass


def carpeta_privada(path):
    path = Path(path)
    if path.is_symlink():
        raise ErrorRespaldo("No se admiten enlaces simbólicos como almacenamiento de respaldo.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise ErrorRespaldo("El directorio de respaldo o claves debe tener permisos 0700.")
    return path.resolve()


def rutas():
    root = Path(settings.BACKUP_ROOT).resolve()
    clave = Path(settings.BACKUP_KEY_FILE).resolve()
    publicas = [Path(settings.STATIC_ROOT).resolve()]
    publicas += [Path(p).resolve() for p in settings.STATICFILES_DIRS]
    if getattr(settings, "MEDIA_ROOT", ""):
        publicas.append(Path(settings.MEDIA_ROOT).resolve())
    if clave.is_relative_to(root) or any(root.is_relative_to(p) or clave.is_relative_to(p) for p in publicas):
        raise ErrorRespaldo("La clave debe estar separada de las copias y ambas fuera de los directorios públicos.")
    if Path(settings.BACKUP_ROOT).is_symlink() or Path(settings.BACKUP_KEY_FILE).is_symlink():
        raise ErrorRespaldo("No se admiten enlaces simbólicos en las rutas configuradas.")
    return carpeta_privada(root), clave


def archivo_privado(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "wb")


def leer_clave(crear=False):
    _, path = rutas()
    carpeta_privada(path.parent)
    if crear and not path.exists():
        try:
            with archivo_privado(path) as archivo:
                archivo.write(os.urandom(32))
        except FileExistsError:
            pass
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise ErrorRespaldo("Falta una clave privada válida. Usa --crear-clave solo para inicializar una nueva instalación.") from None
    with os.fdopen(descriptor, "rb") as archivo:
        info = os.fstat(archivo.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ErrorRespaldo("La clave debe ser un archivo privado con permisos 0600.")
        clave = archivo.read(33)
    if len(clave) != 32:
        raise ErrorRespaldo("La clave no tiene el formato esperado. No la reemplaces si existen copias anteriores.")
    return clave


def derivar(clave, etiqueta):
    return hmac.new(clave, etiqueta, hashlib.sha256).digest()


def cifrar(chunks, salida, clave):
    nonce = os.urandom(12)
    cifrador = Cipher(algorithms.AES(derivar(clave, b"cesfam.sql.aes.v1")), modes.GCM(nonce)).encryptor()
    cifrador.authenticate_additional_data(MAGIC)
    salida.write(MAGIC + nonce)
    for chunk in chunks:
        salida.write(cifrador.update(chunk))
    salida.write(cifrador.finalize())
    salida.write(cifrador.tag)


def descifrar(origen, salida, clave):
    total = os.fstat(origen.fileno()).st_size
    if total < len(MAGIC) + 12 + 16 or origen.read(len(MAGIC)) != MAGIC:
        raise ErrorRespaldo("Formato de respaldo inválido.")
    nonce = origen.read(12)
    origen.seek(-16, os.SEEK_END)
    tag = origen.read(16)
    origen.seek(len(MAGIC) + 12)
    decifrador = Cipher(algorithms.AES(derivar(clave, b"cesfam.sql.aes.v1")), modes.GCM(nonce, tag)).decryptor()
    decifrador.authenticate_additional_data(MAGIC)
    restante = total - len(MAGIC) - 12 - 16
    try:
        while restante:
            chunk = origen.read(min(restante, 1024 * 1024))
            if not chunk:
                raise ErrorRespaldo("Respaldo incompleto.")
            salida.write(decifrador.update(chunk))
            restante -= len(chunk)
        salida.write(decifrador.finalize())
    except Exception:
        # La salida temporal nunca debe importarse antes de que termine la autenticación.
        raise ErrorRespaldo("No se pudo autenticar la copia: archivo alterado, incompleto o clave incorrecta.") from None


def sha256_archivo(path):
    digest = hashlib.sha256()
    with open(path, "rb") as archivo:
        for chunk in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonico(datos):
    return json.dumps(datos, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def guardar_manifiesto(path, datos, clave):
    firma = hmac.new(derivar(clave, b"cesfam.sql.manifest.v1"), canonico(datos), hashlib.sha256).hexdigest()
    with archivo_privado(path) as archivo:
        archivo.write(canonico({"datos": datos, "firma": firma}))


def leer_manifiesto(path, clave):
    try:
        if Path(path).is_symlink():
            raise ValueError
        paquete = json.loads(Path(path).read_bytes())
        firma = hmac.new(derivar(clave, b"cesfam.sql.manifest.v1"), canonico(paquete["datos"]), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, paquete["firma"]):
            raise ValueError
        return paquete["datos"]
    except Exception:
        raise ErrorRespaldo("El manifiesto no es válido o no corresponde a esta clave.") from None

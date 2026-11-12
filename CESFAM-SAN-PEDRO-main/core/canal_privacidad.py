from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from usuarios.utils import es_administrador
from .models import ConfiguracionPrivacidad, HistorialCanalPrivacidad


def configuracion_actual():
    return ConfiguracionPrivacidad.objects.select_related("responsable", "validador").filter(pk=1).first()


def canal_disponible(configuracion):
    return bool(configuracion and configuracion.canal_habilitado
                and configuracion.entidad and configuracion.contacto
                and configuracion.responsable and configuracion.responsable.is_active
                and configuracion.validador and configuracion.validador.is_active
                and configuracion.contacto_validado_por_id == configuracion.validador_id
                and configuracion.contacto_validado_at
                and configuracion.autorizados.filter(is_active=True).exists())


def puede_responder(usuario, configuracion=None):
    configuracion = configuracion if configuracion is not None else configuracion_actual()
    return bool(usuario.is_authenticated and usuario.is_active and configuracion
                and configuracion.autorizados.filter(pk=usuario.pk, is_active=True).exists())


def puede_configurar(usuario, configuracion=None):
    configuracion = configuracion if configuracion is not None else configuracion_actual()
    return bool(es_administrador(usuario) or (usuario.is_authenticated and usuario.is_active
                and configuracion and configuracion.validador_id == usuario.pk))


def bloquear_configuracion():
    ConfiguracionPrivacidad.objects.get_or_create(pk=1)
    return ConfiguracionPrivacidad.objects.select_for_update().get(pk=1)


def validar_revision(configuracion, revision):
    if configuracion.revision != revision:
        raise ValidationError("La configuración cambió. Recarga la página antes de continuar.")


def invalidar_validacion(configuracion):
    configuracion.canal_habilitado = False
    configuracion.contacto_validado_por = None
    configuracion.contacto_validado_at = None
    configuracion.evidencia_validacion = ""


@transaction.atomic
def guardar_configuracion(*, usuario, datos):
    if not es_administrador(usuario):
        raise PermissionDenied
    ids = {datos["validador"].pk} | {u.pk for u in datos["autorizados"]}
    activos = set(get_user_model().objects.select_for_update().filter(pk__in=ids, is_active=True)
                  .order_by("pk").values_list("pk", flat=True))
    if activos != ids:
        raise ValidationError("Las personas designadas deben tener cuentas activas.")
    cfg = bloquear_configuracion()
    validar_revision(cfg, datos["revision"])
    anterior = {"entidad": cfg.entidad, "contacto": cfg.contacto, "validador": cfg.validador_id,
                "autorizados": list(cfg.autorizados.values_list("pk", flat=True))}
    cfg.entidad = datos["entidad"]
    cfg.contacto = datos["contacto"]
    cfg.validador = datos["validador"]
    cfg.autorizados.set(datos["autorizados"])
    invalidar_validacion(cfg)
    cfg.revision += 1
    cfg.save()
    HistorialCanalPrivacidad.objects.create(realizado_por=usuario, accion="CONFIGURACION",
        datos={"anterior": anterior, "nuevo": {"entidad": cfg.entidad, "contacto": cfg.contacto,
               "validador": cfg.validador_id, "autorizados": list(cfg.autorizados.values_list("pk", flat=True))}})


@transaction.atomic
def validar_contacto(*, usuario, revision, evidencia):
    cfg = bloquear_configuracion()
    if not usuario.is_active or cfg.validador_id != usuario.pk:
        raise PermissionDenied
    validar_revision(cfg, revision)
    if not cfg.entidad or not cfg.contacto or not evidencia.strip():
        raise ValidationError("Completa el contacto y registra cómo se verificó su atención institucional.")
    cfg.contacto_validado_por = usuario
    cfg.contacto_validado_at = timezone.now()
    cfg.evidencia_validacion = evidencia.strip()
    cfg.revision += 1
    cfg.save()
    HistorialCanalPrivacidad.objects.create(realizado_por=usuario, accion="CONTACTO_VALIDADO",
                                            datos={"contacto": cfg.contacto, "evidencia": evidencia.strip()})


@transaction.atomic
def cambiar_habilitacion(*, usuario, revision, habilitar):
    if not es_administrador(usuario):
        raise PermissionDenied
    cfg = bloquear_configuracion()
    validar_revision(cfg, revision)
    cfg.canal_habilitado = habilitar
    if habilitar and not canal_disponible(cfg):
        raise ValidationError("Falta responsable activo, contacto validado o personas activas autorizadas para responder.")
    cfg.revision += 1
    cfg.save()
    HistorialCanalPrivacidad.objects.create(realizado_por=usuario,
        accion="CANAL_HABILITADO" if habilitar else "CANAL_SUSPENDIDO", datos={"revision": cfg.revision})

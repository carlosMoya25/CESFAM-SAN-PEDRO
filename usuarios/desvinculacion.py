from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from requerimientos.models import HistorialRequerimiento, Requerimiento
from .models import HistorialAdministracion, Usuario
from .utils import es_administrador, es_tecnico


def pendientes_usuario(usuario):
    return Requerimiento.objects.filter(responsable=usuario).exclude(
        estado__nombre__in=["Cerrado", "Cancelado"])


@transaction.atomic
def desactivar_usuario(*, administrador, usuario_id, reemplazo_id=None, motivo):
    if not administrador.is_active or not es_administrador(administrador):
        raise PermissionDenied
    if administrador.pk == usuario_id:
        raise ValidationError("No puedes desactivar tu propia cuenta.")
    # Bloqueo ordenado de usuarios para coordinar reasignaciones concurrentes.
    ids = sorted({usuario_id} | ({reemplazo_id} if reemplazo_id else set()))
    usuarios = {u.pk: u for u in Usuario.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    usuario = usuarios.get(usuario_id)
    if usuario is None or not usuario.is_active:
        raise ValidationError("La cuenta ya está inactiva o no está disponible.")
    if not motivo.strip():
        raise ValidationError("Indica un motivo administrativo sin datos sensibles.")
    from core.models import ConfiguracionPrivacidad
    configuracion = ConfiguracionPrivacidad.objects.select_for_update().filter(pk=1).first()
    if configuracion and configuracion.responsable_id == usuario.pk:
        raise ValidationError("Antes de desactivar esta cuenta, asigna otra persona en Ley 21.719 → Responsable de atención de privacidad.")
    if configuracion and (configuracion.validador_id == usuario.pk or configuracion.autorizados.filter(pk=usuario.pk).exists()):
        raise ValidationError("Antes de desactivar esta cuenta, reemplázala o retira su autorización en Ley 21.719 → Panel institucional.")
    reemplazo = usuarios.get(reemplazo_id)
    if reemplazo_id and (not reemplazo or reemplazo.pk == usuario.pk or not reemplazo.is_active or not es_tecnico(reemplazo)):
        raise ValidationError("Selecciona otro técnico TI activo como reemplazo.")
    pendientes = list(pendientes_usuario(usuario).select_for_update().select_related("estado"))
    if pendientes and not reemplazo:
        raise ValidationError("Debes seleccionar un técnico TI activo para las solicitudes pendientes.")
    ahora = timezone.now()
    for req in pendientes:
        req.responsable = reemplazo
        req.fecha_asignacion = ahora
        req.save(update_fields=["responsable", "fecha_asignacion", "updated_at"])
        HistorialRequerimiento.objects.create(
            requerimiento=req, usuario=administrador, estado_anterior=req.estado, estado_nuevo=req.estado,
            accion="Reasignación por desactivación de cuenta",
            observacion=f"Responsable anterior: usuario #{usuario.pk}. Nuevo responsable: usuario #{reemplazo.pk}.",
        )
    usuario.is_active = False
    usuario.revision_acceso += 1
    usuario.save(update_fields=["is_active", "revision_acceso"])
    HistorialAdministracion.objects.create(
        accion="DESACTIVAR_USUARIO", administrador=administrador, usuario_afectado=usuario,
        descripcion=f"Cuenta desactivada y sesiones revocadas. Solicitudes reasignadas: {len(pendientes)}. "
                    f"Reemplazo: {reemplazo.pk if reemplazo else 'no requerido'}. Motivo: {motivo.strip()}",
    )
    return len(pendientes)

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from usuarios.utils import es_administrador
from .models import ConfiguracionPrivacidad, HistorialResponsablePrivacidad


@transaction.atomic
def asignar_responsable(*, administrador, responsable_id, motivo, revision):
    if not es_administrador(administrador):
        raise PermissionDenied
    nuevo = get_user_model().objects.select_for_update().filter(pk=responsable_id, is_active=True).first()
    if not nuevo:
        raise ValidationError("Selecciona una cuenta activa como responsable.")
    if not motivo.strip():
        raise ValidationError("Indica el motivo del cambio.")
    ConfiguracionPrivacidad.objects.get_or_create(pk=1)
    configuracion = ConfiguracionPrivacidad.objects.select_for_update().get(pk=1)
    if configuracion.revision != revision:
        raise ValidationError("La asignación cambió mientras revisabas la página. Recarga antes de guardar.")
    if configuracion.responsable_id == nuevo.pk:
        raise ValidationError("Esta persona ya es la responsable actual.")
    HistorialResponsablePrivacidad.objects.create(
        anterior_id=configuracion.responsable_id, nuevo=nuevo, administrador=administrador,
        motivo=motivo.strip(),
    )
    configuracion.responsable = nuevo
    from .canal_privacidad import invalidar_validacion
    invalidar_validacion(configuracion)
    configuracion.revision += 1
    configuracion.save(update_fields=["responsable", "revision", "canal_habilitado", "contacto_validado_por",
                                      "contacto_validado_at", "evidencia_validacion"])

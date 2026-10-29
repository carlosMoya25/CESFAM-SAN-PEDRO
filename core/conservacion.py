"""Propuestas y simulaciones agregadas. Este módulo no ejecuta depuraciones."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import DateTimeField, Max, OuterRef, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from farmacia.models import ImportacionMedicamentos
from requerimientos.models import Requerimiento
from usuarios.models import HistorialAdministracion
from usuarios.utils import es_administrador
from . import privacidad
from .models import (CambioReglaConservacion, ConstanciaPrivacidad, ReglaConservacion,
                     SimulacionConservacion, SolicitudDerecho)


CRITERIOS = {
    "BORRADORES": "Solo borradores sin enviar; antigüedad desde la última actualización.",
    "DERECHOS": "Solo solicitudes respondidas; antigüedad desde la publicación de la respuesta.",
    "IMPORTACIONES": "Solo importaciones pendientes sin movimientos vinculados; desde su creación. Las importadas quedan fuera.",
    "SESIONES": "Solo sesiones vencidas; el plazo se cuenta desde el vencimiento, no desde el último acceso.",
    "REQUERIMIENTOS": "Solo cerrados o cancelados; desde el último cambio del requerimiento o de su historial, el más reciente.",
    "CONSTANCIAS": "Solo avisos anteriores; desde la fecha de lectura. Las constancias del aviso actual quedan fuera.",
    "CUENTAS": "Solo cuentas inactivas; desde la última desactivación registrada en el historial administrativo. Sin esa fecha no se evalúa antigüedad.",
}


def tablas_reglas():
    reglas = {r.categoria: r for r in ReglaConservacion.objects.all()}
    return [{"categoria": categoria, "nombre": nombre, "criterio": CRITERIOS[categoria],
             "regla": reglas.get(categoria)} for categoria, nombre in ReglaConservacion.Categoria.choices]


@transaction.atomic
def guardar_regla(*, usuario, categoria, dias, fundamento, revision):
    if not es_administrador(usuario):
        raise PermissionDenied
    if categoria not in CRITERIOS:
        raise ValidationError("Categoría no disponible.")
    if dias is not None and (not 1 <= dias <= 36500 or not fundamento.strip()):
        raise ValidationError("Indica un plazo entre 1 y 36.500 días y su fundamento institucional.")
    ReglaConservacion.objects.get_or_create(categoria=categoria)
    regla = ReglaConservacion.objects.select_for_update().get(categoria=categoria)
    if regla.revision != revision:
        raise ValidationError("La propuesta cambió en otra pestaña. Recarga antes de guardar.")
    anterior = {"dias": regla.dias, "fundamento": regla.fundamento, "revision": regla.revision}
    if regla.dias == dias and regla.fundamento == fundamento.strip():
        return regla
    regla.dias = dias
    regla.fundamento = fundamento.strip()
    regla.revision += 1
    regla.save(update_fields=["dias", "fundamento", "revision", "actualizada_at"])
    CambioReglaConservacion.objects.create(regla=regla, realizado_por=usuario, anterior=anterior,
        nuevo={"dias": regla.dias, "fundamento": regla.fundamento, "revision": regla.revision})
    return regla


def fuente(categoria, ahora):
    if categoria == "BORRADORES":
        todos = SolicitudDerecho.objects.all()
        return todos, todos.filter(estado="BORRADOR"), "actualizada_at"
    if categoria == "DERECHOS":
        todos = SolicitudDerecho.objects.all()
        return todos, todos.filter(estado="RESPONDIDA"), "respondida_at"
    if categoria == "IMPORTACIONES":
        todos = ImportacionMedicamentos.objects.all()
        return todos, todos.filter(estado="PENDIENTE", movimientos__isnull=True), "creada_at"
    if categoria == "SESIONES":
        todos = Session.objects.all()
        return todos, todos.filter(expire_date__lt=ahora), "expire_date"
    if categoria == "REQUERIMIENTOS":
        todos = Requerimiento.objects.all()
        alcance = todos.filter(estado__nombre__in=["Cerrado", "Cancelado"]).annotate(
            fecha_referencia=Greatest("updated_at", Coalesce(Max("historial__fecha"), "updated_at")))
        return todos, alcance, "fecha_referencia"
    if categoria == "CONSTANCIAS":
        todos = ConstanciaPrivacidad.objects.all()
        return todos, todos.exclude(version=privacidad.VERSION, huella=privacidad.HUELLA), "fecha"
    if categoria == "CUENTAS":
        todos = get_user_model().objects.all()
        ultima_baja = HistorialAdministracion.objects.filter(
            usuario_afectado_id=OuterRef("pk"), accion="DESACTIVAR_USUARIO").order_by("-fecha").values("fecha")[:1]
        alcance = todos.filter(is_active=False).annotate(fecha_referencia=Subquery(ultima_baja, output_field=DateTimeField()))
        return todos, alcance, "fecha_referencia"
    raise ValidationError("Categoría no disponible.")


@transaction.atomic
def simular_conservacion(*, usuario):
    if not es_administrador(usuario):
        raise PermissionDenied
    reglas = list(ReglaConservacion.objects.all())
    if not any(r.dias is not None for r in reglas):
        raise ValidationError("Primero registra al menos una propuesta de plazo para poder simular.")
    por_categoria = {r.categoria: r for r in reglas}
    ahora = timezone.now()
    filas = []
    for categoria, nombre in ReglaConservacion.Categoria.choices:
        regla = por_categoria.get(categoria)
        fila = {"categoria": categoria, "nombre": nombre, "criterio": CRITERIOS[categoria],
                "dias": regla.dias if regla else None, "revision": regla.revision if regla else 0,
                "evaluada": False}
        if regla and regla.dias is not None:
            limite = ahora - timedelta(days=regla.dias)
            todos, alcance, campo_fecha = fuente(categoria, ahora)
            fila.update({"evaluada": True, "fecha_corte": timezone.localtime(limite).strftime("%d/%m/%Y %H:%M"),
                         "total": todos.count(), "en_alcance": alcance.count(),
                         "sin_fecha": alcance.filter(**{f"{campo_fecha}__isnull": True}).count(),
                         "antiguos": alcance.filter(**{f"{campo_fecha}__lt": limite}).count()})
        filas.append(fila)
    # Se guardan criterios y cantidades, nunca nombres, correos, contenidos o identificadores de los datos evaluados.
    return SimulacionConservacion.objects.create(realizado_por=usuario,
        resultado={"version": 1, "momento": ahora.isoformat(), "aviso_version": privacidad.VERSION,
                   "aviso_huella": privacidad.HUELLA, "filas": filas})

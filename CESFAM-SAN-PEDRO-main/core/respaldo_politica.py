from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from usuarios.utils import es_administrador, es_tecnico
from .models import (CambioPoliticaRespaldos, CambioProgramacionRespaldos,
                     PoliticaRespaldos, ProgramacionRespaldos)
from .respaldo_forms import DIAS_SEMANA, PoliticaRespaldosForm


CAMPOS = PoliticaRespaldosForm.Meta.fields


def instantanea(politica):
    datos = {}
    for nombre in CAMPOS:
        valor = getattr(politica, nombre)
        if nombre in ("custodio", "suplente"):
            valor = f"{valor.email} (cuenta {valor.pk})" if valor else "Sin definir"
        elif nombre in ("frecuencia", "ubicacion"):
            valor = getattr(politica, f"get_{nombre}_display")()
        elif nombre == "dia_semana":
            valor = dict(DIAS_SEMANA).get(valor, "Sin definir")
        elif nombre == "hora":
            valor = valor.strftime("%H:%M") if valor else "Sin definir"
        datos[nombre] = str(valor) if valor is not None and valor != "" else "Sin definir"
    datos["revision"] = politica.revision
    return datos


def pendientes_politica(politica):
    pendientes = []
    if politica.frecuencia == "PENDIENTE":
        pendientes.append("Definir la frecuencia de generación.")
    cantidades = [politica.copias_diarias, politica.copias_semanales, politica.copias_mensuales]
    if any(valor is None for valor in cantidades) or not any(cantidades):
        pendientes.append("Completar la conservación de copias; usa 0 para una categoría que no se conservará.")
    if not politica.prueba_cada_dias:
        pendientes.append("Definir cada cuánto se probará la recuperación.")
    for nombre, etiqueta in (("custodio", "custodio principal"), ("suplente", "suplente")):
        persona = getattr(politica, nombre)
        if not persona or not persona.is_active:
            pendientes.append(f"Designar un {etiqueta} con cuenta activa.")
    if not politica.procedimiento_clave:
        pendientes.append("Documentar la custodia separada de la clave.")
    if politica.ubicacion == "PENDIENTE":
        pendientes.append("Confirmar si el destino está en la misma ubicación física.")
    if politica.ubicacion == "MISMA" and not politica.proteccion_adicional:
        pendientes.append("Definir protección adicional frente a la pérdida del lugar.")
    return pendientes


@transaction.atomic
def guardar_politica(*, usuario, datos):
    if not (es_administrador(usuario) or es_tecnico(usuario)):
        raise PermissionDenied
    politica, _ = PoliticaRespaldos.objects.get_or_create(pk=1)
    politica = PoliticaRespaldos.objects.select_for_update().select_related("custodio", "suplente").get(pk=politica.pk)
    if politica.revision != datos["revision"]:
        raise ValidationError("Otra persona cambió esta política. Recarga la página y revisa los valores antes de guardar.")
    # Revalida cuentas dentro de la operación; asignarlas no concede permisos de acceso.
    for nombre in ("custodio", "suplente"):
        persona = datos.get(nombre)
        if persona and not type(persona).objects.filter(pk=persona.pk, is_active=True).exists():
            raise ValidationError("Los custodios deben tener cuentas activas. Revisa la selección.")
    antes = instantanea(politica)
    for nombre in CAMPOS:
        setattr(politica, nombre, datos[nombre])
    politica.revision += 1
    politica.full_clean()
    politica.save()
    programacion = ProgramacionRespaldos.objects.select_for_update().filter(pk=1).first()
    if programacion and programacion.activa:
        programacion.activa = False
        programacion.activada_at = None
        programacion.revision += 1
        programacion.save(update_fields=["activa", "activada_at", "revision"])
        CambioProgramacionRespaldos.objects.create(realizado_por=usuario, activa=False,
            politica_revision=politica.revision, motivo="Suspensión automática por cambio de política: " + datos["motivo"][:900])
    CambioPoliticaRespaldos.objects.create(politica=politica, realizado_por=usuario, motivo=datos["motivo"],
                                          antes=antes, despues=instantanea(politica))
    return politica


from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from organizacion.models import Anexo

from .models import (
    Medicamento,
    LoteMedicamento,
    StockLote,
    MovimientoFarmacia,
    DetalleMovimientoFarmacia,
)


@transaction.atomic
def registrar_entrada_medicamento(
    *,
    medicamento,
    anexo,
    numero_lote,
    fecha_vencimiento,
    cantidad,
    usuario,
    motivo="",
):
    if not usuario.is_authenticated:
        raise ValidationError(
            "El usuario debe iniciar sesión."
        )

    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0:
        raise ValidationError(
            "La cantidad debe ser un entero positivo."
        )

    if fecha_vencimiento < date.today():
        raise ValidationError(
            "No se pueden ingresar medicamentos vencidos."
        )

    if not isinstance(numero_lote, str) or not numero_lote.strip():
        raise ValidationError(
            "Debe ingresar un número de lote."
        )

    numero_lote = numero_lote.strip()

    if not Medicamento.objects.filter(
        pk=medicamento.pk,
        activo=True,
        articulo__activo=True,
    ).exists():
        raise ValidationError(
            "El medicamento no está activo."
        )

    if not Anexo.objects.filter(
        pk=anexo.pk,
        activo=True,
    ).exists():
        raise ValidationError(
            "La ubicación no está activa."
        )

    # Buscar o registrar el lote.
    lote, creado = LoteMedicamento.objects.get_or_create(
        medicamento=medicamento,
        numero_lote=numero_lote,
        defaults={
            "fecha_vencimiento": fecha_vencimiento,
            "activo": True,
        },
    )

    if not lote.activo:
        raise ValidationError(
            "El lote se encuentra inactivo."
        )

    if lote.fecha_vencimiento != fecha_vencimiento:
        raise ValidationError(
            "El lote ya existe con otra fecha de vencimiento."
        )

    # Crear el registro de stock si todavía no existe.
    stock, _ = StockLote.objects.get_or_create(
        lote=lote,
        anexo=anexo,
        defaults={"cantidad": 0},
    )

    # Incremento atómico para evitar perder actualizaciones.
    StockLote.objects.filter(pk=stock.pk).update(
        cantidad=F("cantidad") + cantidad
    )

    # Registrar movimiento de farmacia.
    movimiento = MovimientoFarmacia.objects.create(
        tipo="ENTRADA",
        anexo_origen=None,
        anexo_destino=anexo,
        usuario=usuario,
        motivo=motivo or "Ingreso de medicamentos",
    )

    DetalleMovimientoFarmacia.objects.create(
        movimiento=movimiento,
        lote=lote,
        cantidad=cantidad,
    )

    return movimiento

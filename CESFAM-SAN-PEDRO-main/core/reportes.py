"""
Agregación de datos para los paneles de reportes (vista general, soporte TI,
insumos y farmacia) y para los informes institucionales en PDF.

Centralizar estas consultas aquí evita duplicar lógica de filtrado entre los
distintos paneles y los informes PDF, y asegura que todos muestren exactamente
las mismas cifras para un mismo rango de fechas y una misma ubicación.
"""
from collections import Counter
from datetime import datetime, time, timedelta

from django.db import connections
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from farmacia.models import MovimientoFarmacia, StockLote
from inventario.models import DetalleMovimiento, MovimientoInventario, StockAnexo
from requerimientos.models import Requerimiento

DIAS_RANGO_POR_DEFECTO = 30
DIAS_ALERTA_VENCIMIENTO = 30


def rango_por_defecto(dias=DIAS_RANGO_POR_DEFECTO):
    """Últimos ``dias`` días (incluyendo hoy) cuando no se indica un rango."""
    hoy = timezone.localdate()
    return hoy - timedelta(days=dias - 1), hoy


def _filtrar_por_fecha(queryset, campo, desde, hasta):
    if desde:
        inicio = timezone.make_aware(datetime.combine(desde, time.min))
        queryset = queryset.filter(**{f"{campo}__gte": inicio})
    if hasta:
        fin = timezone.make_aware(datetime.combine(hasta, time.max))
        queryset = queryset.filter(**{f"{campo}__lte": fin})
    return queryset


def serie_semanal(queryset, campo_fecha, desde, hasta):
    """Cuenta de lunes a domingo, recortando las etiquetas al período filtrado."""
    conexion = connections[queryset.db]
    if conexion.vendor == "mysql" and not conexion.features.has_zoneinfo_database:
        # shortcut: agrupar fechas en Django mientras MySQL carezca de tablas de zonas horarias.
        fechas = queryset.order_by().values_list(campo_fecha, flat=True).iterator()
        totales = Counter()
        for fecha in fechas:
            dia = timezone.localtime(fecha).date()
            totales[dia - timedelta(days=dia.weekday())] += 1
    else:
        conteo = (
            queryset.order_by()
            .annotate(semana=TruncWeek(campo_fecha))
            .values("semana")
            .annotate(total=Count("id"))
        )
        totales = {fila["semana"].date(): fila["total"] for fila in conteo}

    serie = []
    lunes = desde - timedelta(days=desde.weekday())
    while lunes <= hasta:
        fin = lunes + timedelta(days=min(6, (hasta - lunes).days))
        serie.append({
            "desde": max(desde, lunes),
            "hasta": fin,
            "total": totales.get(lunes, 0),
        })
        if fin == hasta:
            break
        lunes += timedelta(days=7)
    return serie


def datos_requerimientos(desde, hasta, anexo=None):
    """Métricas de solicitudes TI para el rango y la ubicación indicados."""
    base = Requerimiento.objects.select_related("estado", "prioridad", "anexo", "tipo_requerimiento", "responsable")
    base = _filtrar_por_fecha(base, "fecha_solicitud", desde, hasta)
    if anexo:
        base = base.filter(anexo=anexo)

    por_estado = {
        fila["estado__nombre"]: fila["total"]
        for fila in base.values("estado__nombre").annotate(total=Count("id"))
    }

    pendientes = por_estado.get("Pendiente", 0)
    en_proceso = por_estado.get("En proceso", 0)
    resueltos = por_estado.get("Resuelto", 0)
    # "En atención" agrupa lo asignado y lo que ya está en proceso.
    en_atencion = en_proceso + por_estado.get("Asignado", 0)
    # "Resueltas" agrupa lo resuelto y lo ya cerrado.
    finalizados = resueltos + por_estado.get("Cerrado", 0)

    por_prioridad = {
        fila["prioridad__nombre"]: fila["total"]
        for fila in base.values("prioridad__nombre").annotate(total=Count("id"))
    }

    top_tipos = list(
        base.values("tipo_requerimiento__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")[:6]
    )

    return {
        "total": base.count(),
        "pendientes": pendientes,
        "en_proceso": en_proceso,
        "resueltos": resueltos,
        "en_atencion": en_atencion,
        "finalizados": finalizados,
        "por_estado": por_estado,
        "por_prioridad": por_prioridad,
        "top_tipos": top_tipos,
        "serie_semanal": serie_semanal(base, "fecha_solicitud", desde, hasta),
        "listado": base.order_by("-fecha_solicitud"),
    }


def datos_insumos(desde, hasta, anexo=None):
    """Métricas de inventario general: artículos con stock bajo y movimiento del período."""
    stocks = StockAnexo.objects.select_related("articulo", "anexo").filter(
        articulo__activo=True,
        articulo__medicamento__isnull=True,
        articulo__saldos_pendientes_farmacia__isnull=True,
    )
    if anexo:
        stocks = stocks.filter(anexo=anexo)

    stock_bajo = stocks.filter(
        cantidad__gt=0,
        cantidad__lte=F("articulo__stock_minimo"),
    ).order_by("cantidad")

    sin_stock = stocks.filter(cantidad=0).order_by("articulo__nombre")

    movimientos = MovimientoInventario.objects.all()
    movimientos = _filtrar_por_fecha(movimientos, "fecha", desde, hasta)
    if anexo:
        movimientos = movimientos.filter(Q(anexo_origen=anexo) | Q(anexo_destino=anexo))

    por_tipo = list(
        movimientos.values("tipo_movimiento__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return {
        "total_articulos": stocks.values("articulo").distinct().count(),
        "stock_bajo": stock_bajo,
        "total_stock_bajo": stock_bajo.count(),
        "sin_stock": sin_stock,
        "total_sin_stock": sin_stock.count(),
        "detalle_movimientos": DetalleMovimiento.objects.filter(movimiento__in=movimientos)
        .select_related("articulo", "movimiento__tipo_movimiento")
        .order_by("-movimiento__fecha", "-pk"),
        "movimientos_total": movimientos.count(),
        "por_tipo_movimiento": por_tipo,
        "serie_semanal": serie_semanal(movimientos, "fecha", desde, hasta),
    }


def datos_farmacia(desde, hasta, anexo=None, dias_alerta=DIAS_ALERTA_VENCIMIENTO):
    """Métricas de farmacia: lotes por vencer/vencidos y movimiento del período."""
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=dias_alerta)

    stocks = StockLote.objects.select_related(
        "lote__medicamento__articulo", "anexo"
    ).filter(
        lote__activo=True,
        lote__medicamento__activo=True,
        lote__medicamento__articulo__activo=True,
        anexo__activo=True,
    )
    if anexo:
        stocks = stocks.filter(anexo=anexo)

    con_stock = stocks.filter(cantidad__gt=0)

    utilizable = con_stock.filter(lote__fecha_vencimiento__gte=hoy)

    por_vencer = con_stock.filter(
        lote__fecha_vencimiento__range=(hoy, limite)
    ).order_by("lote__fecha_vencimiento")

    vencidos = con_stock.filter(
        lote__fecha_vencimiento__lt=hoy
    ).order_by("lote__fecha_vencimiento")

    movimientos = MovimientoFarmacia.objects.all()
    movimientos = _filtrar_por_fecha(movimientos, "fecha", desde, hasta)
    if anexo:
        movimientos = movimientos.filter(Q(anexo_origen=anexo) | Q(anexo_destino=anexo))

    etiquetas_tipo = dict(MovimientoFarmacia.TIPOS_MOVIMIENTO)
    por_tipo = [
        {"tipo": etiquetas_tipo.get(fila["tipo"], fila["tipo"]), "total": fila["total"]}
        for fila in movimientos.values("tipo").annotate(total=Count("id")).order_by("-total")
    ]

    return {
        "dias_alerta": dias_alerta,
        "total_medicamentos": stocks.values("lote__medicamento").distinct().count(),
        "unidades_disponibles": con_stock.aggregate(total=Sum("cantidad"))["total"] or 0,
        "unidades_utilizables": utilizable.aggregate(total=Sum("cantidad"))["total"] or 0,
        "lotes_por_vencer": por_vencer,
        "total_por_vencer": por_vencer.values("lote").distinct().count(),
        "lotes_vencidos": vencidos,
        "total_vencidos": vencidos.values("lote").distinct().count(),
        "movimientos_total": movimientos.count(),
        "por_tipo_movimiento": por_tipo,
        "serie_semanal": serie_semanal(movimientos, "fecha", desde, hasta),
    }

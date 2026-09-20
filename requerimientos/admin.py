from django.contrib import admin

from .models import (
    EstadoRequerimiento,
    HistorialRequerimiento,
    Prioridad,
    Requerimiento,
    TipoRequerimiento,
)


@admin.register(TipoRequerimiento)
class TipoRequerimientoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(Prioridad)
class PrioridadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nivel")
    ordering = ("nivel",)


@admin.register(EstadoRequerimiento)
class EstadoRequerimientoAdmin(admin.ModelAdmin):
    list_display = ("nombre",)


@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titulo",
        "solicitante",
        "responsable",
        "prioridad",
        "estado",
        "anexo",
        "fecha_solicitud",
    )

    list_filter = (
        "estado",
        "prioridad",
        "tipo_requerimiento",
        "anexo",
    )

    search_fields = (
        "titulo",
        "descripcion",
        "solicitante__email",
        "responsable__email",
    )

    readonly_fields = (
        "fecha_solicitud",
        "created_at",
        "updated_at",
    )


@admin.register(HistorialRequerimiento)
class HistorialRequerimientoAdmin(admin.ModelAdmin):
    list_display = (
        "requerimiento",
        "accion",
        "usuario",
        "estado_anterior",
        "estado_nuevo",
        "fecha",
    )

    list_filter = (
        "estado_anterior",
        "estado_nuevo",
    )

    readonly_fields = ("fecha",)
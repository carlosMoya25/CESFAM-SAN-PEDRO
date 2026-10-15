from django.contrib import admin

from .models import (
    Medicamento,
    LoteMedicamento,
    StockLote,
    MovimientoFarmacia,
    DetalleMovimientoFarmacia,
)


@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display = (
        "articulo",
        "principio_activo",
        "concentracion",
        "forma_farmaceutica",
        "activo",
    )

    search_fields = (
        "articulo__nombre",
        "principio_activo",
    )

    list_filter = (
        "activo",
        "requiere_receta",
    )


@admin.register(LoteMedicamento)
class LoteMedicamentoAdmin(admin.ModelAdmin):
    list_display = (
        "medicamento",
        "numero_lote",
        "fecha_vencimiento",
        "activo",
    )

    search_fields = (
        "medicamento__articulo__nombre",
        "numero_lote",
    )


@admin.register(StockLote)
class StockLoteAdmin(admin.ModelAdmin):
    list_display = (
        "lote",
        "anexo",
        "cantidad",
    )

    readonly_fields = (
        "lote",
        "anexo",
        "cantidad",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DetalleMovimientoInline(admin.TabularInline):
    model = DetalleMovimientoFarmacia
    extra = 0
    can_delete = False
    readonly_fields = ("lote", "cantidad")

    def has_add_permission(self, request, obj):
        return False


@admin.register(MovimientoFarmacia)
class MovimientoFarmaciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tipo",
        "anexo_origen",
        "anexo_destino",
        "usuario",
        "fecha",
    )

    readonly_fields = (
        "tipo",
        "anexo_origen",
        "anexo_destino",
        "usuario",
        "motivo",
        "fecha",
    )

    inlines = [DetalleMovimientoInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
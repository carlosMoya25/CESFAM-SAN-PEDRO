from django.contrib import admin

from .models import ConstanciaPrivacidad, EventoAuditoria
from usuarios.utils import puede_ver_auditoria


@admin.register(ConstanciaPrivacidad)
class ConstanciaPrivacidadAdmin(admin.ModelAdmin):
    list_display = ("usuario", "version", "fecha")
    list_filter = ("version",)
    search_fields = ("usuario__email",)
    readonly_fields = ("usuario", "version", "huella", "texto", "declaracion", "fecha")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "modulo", "accion", "resultado", "modelo", "objeto_id")
    list_filter = ("modulo", "resultado", "origen")
    search_fields = ("=objeto_id", "=vista", "=modelo")
    list_select_related = ("usuario",)

    def has_module_permission(self, request):
        return puede_ver_auditoria(request.user)

    def has_view_permission(self, request, obj=None):
        return puede_ver_auditoria(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

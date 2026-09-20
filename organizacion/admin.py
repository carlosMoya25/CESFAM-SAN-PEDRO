from django.contrib import admin
from .models import Anexo, Departamento


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "direccion", "telefono", "activo")
    search_fields = ("nombre", "direccion")
    list_filter = ("activo",)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)
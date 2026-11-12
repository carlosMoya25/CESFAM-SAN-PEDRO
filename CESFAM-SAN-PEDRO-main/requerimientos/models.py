from django.conf import settings
from django.db import models


class TipoRequerimiento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de requerimiento"
        verbose_name_plural = "Tipos de requerimiento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Prioridad(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    nivel = models.PositiveIntegerField(unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Prioridad"
        verbose_name_plural = "Prioridades"
        ordering = ["nivel"]

    def __str__(self):
        return self.nombre


class EstadoRequerimiento(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Estado de requerimiento"
        verbose_name_plural = "Estados de requerimiento"
        ordering = ["id"]

    def __str__(self):
        return self.nombre


class Requerimiento(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requerimientos_solicitados",
    )

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requerimientos_asignados",
    )

    anexo = models.ForeignKey(
        "organizacion.Anexo",
        on_delete=models.PROTECT,
        related_name="requerimientos",
    )

    departamento = models.ForeignKey(
        "organizacion.Departamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requerimientos",
    )

    tipo_requerimiento = models.ForeignKey(
        TipoRequerimiento,
        on_delete=models.PROTECT,
        related_name="requerimientos",
    )

    prioridad = models.ForeignKey(
        Prioridad,
        on_delete=models.PROTECT,
        related_name="requerimientos",
    )

    estado = models.ForeignKey(
        EstadoRequerimiento,
        on_delete=models.PROTECT,
        related_name="requerimientos",
    )

    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    solucion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requerimiento"
        verbose_name_plural = "Requerimientos"
        ordering = ["-fecha_solicitud"]

    def __str__(self):
        return f"#{self.pk} - {self.titulo}"


class HistorialRequerimiento(models.Model):
    requerimiento = models.ForeignKey(
        Requerimiento,
        on_delete=models.CASCADE,
        related_name="historial",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="acciones_requerimientos",
    )

    estado_anterior = models.ForeignKey(
        EstadoRequerimiento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historial_estado_anterior",
    )

    estado_nuevo = models.ForeignKey(
        EstadoRequerimiento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historial_estado_nuevo",
    )

    accion = models.CharField(max_length=150)
    observacion = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de requerimiento"
        verbose_name_plural = "Historial de requerimientos"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.requerimiento} - {self.accion}"
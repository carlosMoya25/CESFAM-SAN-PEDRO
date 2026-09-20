from django.db import models

from django.db import models


class Anexo(models.Model):
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Departamento(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
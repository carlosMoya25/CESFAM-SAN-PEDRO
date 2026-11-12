from django.db import models





class Anexo(models.Model):

    TIPO_CESFAM = "CESFAM"
    TIPO_FARMACIA = "FARMACIA"
    TIPO_ANEXO = "ANEXO"

    TIPOS_ESTABLECIMIENTO = [
        (TIPO_CESFAM, "CESFAM"),
        (TIPO_FARMACIA, "Farmacia Central"),
        (TIPO_ANEXO, "Anexo"),
    ]

    nombre = models.CharField(max_length=150)

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_ESTABLECIMIENTO,
        default=TIPO_ANEXO,
    )

    direccion = models.CharField(
        max_length=255,
        blank=True
    )

    telefono = models.CharField(
        max_length=30,
        blank=True
    )

    activo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ubicación de inventario"
        verbose_name_plural = "Ubicaciones de inventario"
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
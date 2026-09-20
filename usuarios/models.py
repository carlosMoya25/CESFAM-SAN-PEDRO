from django.db import models

from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UsuarioManager

class Usuario(AbstractUser):
    username = None

    email = models.EmailField(
        "correo electrónico",
        unique=True
    )

    nombres = models.CharField(
        "nombres",
        max_length=100
    )

    apellido_paterno = models.CharField(
        "apellido paterno",
        max_length=100
    )

    apellido_materno = models.CharField(
        "apellido materno",
        max_length=100,
        blank=True
    )

    telefono = models.CharField(
        max_length=30,
        blank=True
    )

    anexo = models.ForeignKey(
        "organizacion.Anexo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios"
    )

    departamento = models.ForeignKey(
        "organizacion.Departamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombres", "apellido_paterno"]
    objects = UsuarioManager()
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["apellido_paterno", "nombres"]

    def __str__(self):
        return f"{self.nombres} {self.apellido_paterno} ({self.email})"
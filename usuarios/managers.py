from django.contrib.auth.base_user import BaseUserManager


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")

        email = self.normalize_email(email)

        usuario = self.model(
            email=email,
            **extra_fields
        )

        usuario.set_password(password)
        usuario.save(using=self._db)

        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(
            email,
            password,
            **extra_fields
        )

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(
                "El superusuario debe tener is_staff=True."
            )

        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                "El superusuario debe tener is_superuser=True."
            )

        return self._create_user(
            email,
            password,
            **extra_fields
        )
def tiene_rol(usuario, rol):
    if not usuario.is_authenticated:
        return False

    return usuario.groups.filter(name=rol).exists()


def es_tecnico(usuario):
    return tiene_rol(usuario, "Técnico TI")


def es_administrador(usuario):
    return tiene_rol(usuario, "Administrador") or usuario.is_superuser
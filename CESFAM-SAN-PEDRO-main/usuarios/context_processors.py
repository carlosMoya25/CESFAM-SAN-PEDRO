from .utils import puede_gestionar_farmacia, puede_gestionar_inventario, puede_ver_auditoria


def permisos_modulos(request):
    return {
        "puede_gestionar_farmacia": puede_gestionar_farmacia(request.user),
        "puede_gestionar_inventario": puede_gestionar_inventario(request.user),
        "puede_ver_auditoria": puede_ver_auditoria(request.user),
    }

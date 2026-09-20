from django.urls import path

from . import views


urlpatterns = [
    path(
        "nuevo/",
        views.crear_requerimiento,
        name="crear_requerimiento",
    ),

    path(
        "mis-solicitudes/",
        views.mis_requerimientos,
        name="mis_requerimientos",
    ),

    path(
        "<int:pk>/",
        views.detalle_requerimiento,
        name="detalle_requerimiento",
    ),

    path(
    "tecnico/",
    views.panel_tecnico,
    name="panel_tecnico",
),

path(
    "tecnico/<int:pk>/",
    views.detalle_tecnico,
    name="detalle_tecnico",
),
path(
    "tecnico/<int:pk>/iniciar/",
    views.iniciar_atencion,
    name="iniciar_atencion",
),

path(
    "tecnico/<int:pk>/observacion/",
    views.agregar_observacion,
    name="agregar_observacion",
),

path(
    "tecnico/<int:pk>/resolver/",
    views.resolver_requerimiento,
    name="resolver_requerimiento",
),

path(
    "tecnico/<int:pk>/cerrar/",
    views.cerrar_requerimiento,
    name="cerrar_requerimiento",
),

]
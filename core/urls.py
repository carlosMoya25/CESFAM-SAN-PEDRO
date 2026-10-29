from django.urls import path
from . import views
from . import privacidad_views
from . import derechos_views
from . import canal_views, gestion_derechos_views
from . import conservacion_views
from . import respaldo_views
from . import auditoria_views


urlpatterns = [
    path("auditoria/", auditoria_views.panel_auditoria, name="panel_auditoria"),
    path("auditoria/<int:pk>/", auditoria_views.detalle_auditoria, name="detalle_auditoria"),
    path("privacidad/respaldos/", respaldo_views.panel_respaldos, name="panel_respaldos"),
    path("privacidad/respaldos/programacion/", respaldo_views.configurar_programacion_respaldos, name="configurar_programacion_respaldos"),
    path("privacidad/respaldos/historial/", respaldo_views.historial_descargas_respaldos, name="historial_descargas_respaldos"),
    path("privacidad/respaldos/<uuid:identificador>/descargar/", respaldo_views.descargar_respaldo, name="descargar_respaldo"),
    path("privacidad/conservacion/", conservacion_views.panel_conservacion, name="panel_conservacion"),
    path("privacidad/conservacion/reglas/<str:categoria>/", conservacion_views.editar_regla_conservacion, name="editar_regla_conservacion"),
    path("privacidad/conservacion/simular/", conservacion_views.ejecutar_simulacion_conservacion, name="simular_conservacion"),
    path("privacidad/conservacion/informes/<int:pk>/", conservacion_views.detalle_simulacion_conservacion, name="detalle_simulacion_conservacion"),
    path("privacidad/institucion/", canal_views.panel_institucional, name="panel_institucional"),
    path("privacidad/atencion/", gestion_derechos_views.bandeja_derechos, name="bandeja_derechos"),
    path("privacidad/atencion/<uuid:identificador>/", gestion_derechos_views.gestionar_derecho, name="gestionar_derecho"),
    path("privacidad/mis-datos/<uuid:identificador>/enviar/", derechos_views.enviar_derecho, name="enviar_derecho"),
    path("privacidad/mis-datos/", derechos_views.mis_derechos, name="mis_derechos"),
    path("privacidad/mis-datos/nueva/", derechos_views.formulario_derecho, name="crear_derecho"),
    path("privacidad/mis-datos/<uuid:identificador>/", derechos_views.detalle_derecho, name="detalle_derecho"),
    path("privacidad/mis-datos/<uuid:identificador>/editar/", derechos_views.formulario_derecho, name="editar_derecho"),
    path("privacidad/responsable/", privacidad_views.cambiar_responsable_privacidad, name="cambiar_responsable_privacidad"),
    path("privacidad/", privacidad_views.aviso_privacidad, name="aviso_privacidad"),
    path("privacidad/confirmar/", privacidad_views.confirmar_privacidad, name="confirmar_privacidad"),
    path("", views.dashboard, name="dashboard"),
]

from django.urls import path

from . import views


app_name = "usuarios"


urlpatterns = [

    path(
        "seguridad/",
        views.panel_seguridad,
        name="seguridad"
    ),

    path(
        "seguridad/desbloquear/<int:pk>/",
        views.desbloquear_usuario,
        name="desbloquear_usuario"
    ),

]
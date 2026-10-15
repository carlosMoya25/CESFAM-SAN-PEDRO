
from django.urls import path
from . import views

app_name = "farmacia"

urlpatterns = [
    path(
        "",
        views.dashboard,
        name="dashboard",
    ),

    path(
        "entradas/nueva/",
        views.registrar_entrada,
        name="registrar_entrada",
    ),

    path(
        "medicamentos/",
        views.lista_medicamentos,
        name="lista_medicamentos",
    ),

    path(
        "medicamentos/nuevo/",
        views.crear_medicamento,
        name="crear_medicamento",
    ),

    path(
        "medicamentos/<int:pk>/",
        views.detalle_medicamento,
        name="detalle_medicamento",
    ),

    path(
        "medicamentos/<int:pk>/editar/",
        views.editar_medicamento,
        name="editar_medicamento",
    ),

    path(
        "medicamentos/<int:pk>/estado/",
        views.cambiar_estado_medicamento,
        name="cambiar_estado_medicamento",
    ),
]

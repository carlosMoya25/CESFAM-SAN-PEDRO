from config import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum, Max
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import HistorialSeguridad

from axes.models import AccessAttempt
from axes.utils import reset

from .utils import es_administrador


Usuario = get_user_model()


def panel_seguridad(request):
    """
    Panel de seguridad de acceso.

    Solo puede ser utilizado por administradores.
    Muestra usuarios que poseen intentos fallidos registrados
    por django-axes.
    """

    if not es_administrador(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder al panel de seguridad."
        )

    # Intentos registrados por Axes agrupados por username.
    intentos_axes = (
        AccessAttempt.objects
        .values("username")
        .annotate(
            intentos=Sum("failures_since_start"),
            ultimo_intento=Max("attempt_time"),
        )
        .order_by("-ultimo_intento")
    )

    # Convertimos los registros en información útil para la plantilla.
    incidencias = []

    for intento in intentos_axes:

        username = intento["username"]
        cantidad = intento["intentos"] or 0

        if not username:
            continue

        usuario = Usuario.objects.filter(
            email__iexact=username
        ).first()

        incidencias.append({
            "usuario": usuario,
            "username": username,
            "intentos": cantidad,
            "ultimo_intento": intento["ultimo_intento"],

            # Nuestro límite actual de Axes es 5.
            "bloqueado": cantidad >= settings.AXES_FAILURE_LIMIT,
        })

    historial = (
        HistorialSeguridad.objects.select_related("usuario_afectado", "realizado_por").all()[:20]
    )


    contexto = {
        "incidencias": incidencias,
        "total_incidencias": len(incidencias),
        "total_bloqueados": sum(
            1 for item in incidencias if item["bloqueado"]
        ),
        "historial": historial,
    }

    return render(
        request,
        "usuarios/seguridad.html",
        contexto
    )


@require_POST
def desbloquear_usuario(request, pk):

    if not es_administrador(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para realizar esta acción."
        )

    usuario = get_object_or_404(
        Usuario,
        pk=pk
    )

    # ---------------------------------------------------------
    # Determinar si estaba bloqueado o solamente tenía intentos
    # ---------------------------------------------------------

    intento = (
        AccessAttempt.objects
        .filter(username__iexact=usuario.email)
        .aggregate(
            total=Sum("failures_since_start")
        )
    )

    cantidad_intentos = intento["total"] or 0

    estaba_bloqueado = (
        cantidad_intentos >= settings.AXES_FAILURE_LIMIT
    )

    # ---------------------------------------------------------
    # Reiniciar Axes
    # ---------------------------------------------------------

    reset(username=usuario.email)

    # ---------------------------------------------------------
    # Registrar auditoría
    # ---------------------------------------------------------

    if estaba_bloqueado:

        tipo_accion = "DESBLOQUEO_USUARIO"

        descripcion = (
            f"Se desbloqueó manualmente al usuario "
            f"{usuario.email}, quien registraba "
            f"{cantidad_intentos} intentos fallidos."
        )

    else:

        tipo_accion = "REINICIO_INTENTOS"

        descripcion = (
            f"Se reiniciaron manualmente los intentos fallidos "
            f"del usuario {usuario.email}. "
            f"Intentos registrados antes del reinicio: "
            f"{cantidad_intentos}."
        )

    HistorialSeguridad.objects.create(
        tipo_accion=tipo_accion,
        usuario_afectado=usuario,
        email_afectado=usuario.email,
        realizado_por=request.user,
        descripcion=descripcion,
    )

    # ---------------------------------------------------------
    # Mensaje
    # ---------------------------------------------------------

    if estaba_bloqueado:

        messages.success(
            request,
            f"El usuario {usuario.email} fue desbloqueado correctamente."
        )

    else:

        messages.success(
            request,
            f"Los intentos fallidos de {usuario.email} fueron reiniciados."
        )

    return redirect("usuarios:seguridad")
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RequerimientoForm, ObservacionRequerimientoForm, RequerimientoForm, ResolverRequerimientoForm
from .models import EstadoRequerimiento, HistorialRequerimiento, Requerimiento

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.utils import timezone

from usuarios.utils import es_administrador, es_tecnico

@login_required
def crear_requerimiento(request):

    if request.method == "POST":
        form = RequerimientoForm(request.POST)

        if form.is_valid():
            requerimiento = form.save(commit=False)

            requerimiento.solicitante = request.user

            requerimiento.estado = EstadoRequerimiento.objects.get(
                nombre="Pendiente"
            )

            requerimiento.save()

            HistorialRequerimiento.objects.create(
                requerimiento=requerimiento,
                usuario=request.user,
                estado_nuevo=requerimiento.estado,
                accion="Requerimiento creado",
                observacion="Solicitud ingresada al sistema.",
            )

            return redirect(
                "detalle_requerimiento",
                pk=requerimiento.pk
            )

    else:
        form = RequerimientoForm(
            initial={
                "anexo": request.user.anexo,
                "departamento": request.user.departamento,
            }
        )

    return render(
        request,
        "requerimientos/crear.html",
        {"form": form},
    )


@login_required
def mis_requerimientos(request):

    requerimientos = (
        Requerimiento.objects
        .filter(solicitante=request.user)
        .select_related(
            "estado",
            "prioridad",
            "tipo_requerimiento",
            "responsable",
            "anexo",
        )
    )

    return render(
        request,
        "requerimientos/mis_requerimientos.html",
        {"requerimientos": requerimientos},
    )


@login_required
def detalle_requerimiento(request, pk):

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_related(
            "solicitante",
            "responsable",
            "estado",
            "prioridad",
            "tipo_requerimiento",
            "anexo",
            "departamento",
        ),
        pk=pk,
        solicitante=request.user,
    )

    historial = (
        requerimiento.historial
        .select_related(
            "usuario",
            "estado_anterior",
            "estado_nuevo",
        )
        .all()
    )

    return render(
        request,
        "requerimientos/detalle.html",
        {
            "requerimiento": requerimiento,
            "historial": historial,
        },
    )

@login_required
def panel_tecnico(request):

    if not es_tecnico(request.user) and not es_administrador(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder al panel técnico."
        )

    requerimientos = (
        Requerimiento.objects
        .select_related(
            "solicitante",
            "responsable",
            "estado",
            "prioridad",
            "tipo_requerimiento",
            "anexo",
            "departamento",
        )
        .order_by("-fecha_solicitud")
    )

    pendientes = requerimientos.filter(
        responsable__isnull=True,
        estado__nombre="Pendiente",
    )

    mis_asignados = requerimientos.filter(
        responsable=request.user
    ).exclude(
        estado__nombre__in=["Cerrado", "Cancelado"]
    )

    contexto = {
        "requerimientos": requerimientos,
        "pendientes": pendientes,
        "mis_asignados": mis_asignados,
    }

    return render(
        request,
        "requerimientos/panel_tecnico.html",
        contexto,
    )

@login_required
@transaction.atomic
def asignarme_requerimiento(request, pk):

    if request.method != "POST":
        return HttpResponseForbidden(
            "Operación no permitida."
        )

    if not es_tecnico(request.user):
        return HttpResponseForbidden(
            "Solo un Técnico TI puede asignarse requerimientos."
        )

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_for_update(),
        pk=pk,
    )

    if requerimiento.responsable_id is not None:
        messages.error(
            request,
            "Este requerimiento ya fue asignado a otro técnico."
        )

        return redirect("panel_tecnico")

    if requerimiento.estado.nombre != "Pendiente":
        messages.error(
            request,
            "El requerimiento ya no se encuentra pendiente."
        )

        return redirect("panel_tecnico")

    estado_anterior = requerimiento.estado

    estado_asignado = EstadoRequerimiento.objects.get(
        nombre="Asignado"
    )

    requerimiento.responsable = request.user
    requerimiento.estado = estado_asignado
    requerimiento.fecha_asignacion = timezone.now()

    requerimiento.save(
        update_fields=[
            "responsable",
            "estado",
            "fecha_asignacion",
            "updated_at",
        ]
    )

    HistorialRequerimiento.objects.create(
        requerimiento=requerimiento,
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_asignado,
        accion="Requerimiento asignado",
        observacion=(
            "El Técnico TI se asignó el requerimiento."
        ),
    )

    messages.success(
        request,
        f"El requerimiento #{requerimiento.id} fue asignado correctamente."
    )

    return redirect(
        "detalle_tecnico",
        pk=requerimiento.pk,
    )

@login_required
def detalle_tecnico(request, pk):

    if not es_tecnico(request.user) and not es_administrador(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para consultar este requerimiento."
        )

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_related(
            "solicitante",
            "responsable",
            "estado",
            "prioridad",
            "tipo_requerimiento",
            "anexo",
            "departamento",
        ),
        pk=pk,
    )

    historial = (
        requerimiento.historial
        .select_related(
            "usuario",
            "estado_anterior",
            "estado_nuevo",
        )
        .all()
    )

    puede_modificar = (
        requerimiento.responsable_id == request.user.id
        or es_administrador(request.user)
    )

    contexto = {
        "requerimiento": requerimiento,
        "historial": historial,
        "puede_modificar": puede_modificar,
    }

    return render(
        request,
        "requerimientos/detalle_tecnico.html",
        contexto,
    )

@login_required
@transaction.atomic
def iniciar_atencion(request, pk):

    if request.method != "POST":
        return HttpResponseForbidden("Operación no permitida.")

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_for_update(),
        pk=pk,
    )

    if (
        requerimiento.responsable_id != request.user.id
        and not es_administrador(request.user)
    ):
        return HttpResponseForbidden(
            "No eres responsable de este requerimiento."
        )

    if requerimiento.estado.nombre != "Asignado":
        messages.error(
            request,
            "Solo se puede iniciar un requerimiento que esté asignado."
        )
        return redirect("detalle_tecnico", pk=pk)

    estado_anterior = requerimiento.estado

    estado_nuevo = EstadoRequerimiento.objects.get(
        nombre="En proceso"
    )

    requerimiento.estado = estado_nuevo
    requerimiento.save(
        update_fields=["estado", "updated_at"]
    )

    HistorialRequerimiento.objects.create(
        requerimiento=requerimiento,
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        accion="Atención iniciada",
        observacion="El técnico inició la atención del requerimiento.",
    )

    messages.success(
        request,
        "El requerimiento ahora está en proceso."
    )

    return redirect("detalle_tecnico", pk=pk)

@login_required
def agregar_observacion(request, pk):

    requerimiento = get_object_or_404(
        Requerimiento,
        pk=pk,
    )

    if (
        requerimiento.responsable_id != request.user.id
        and not es_administrador(request.user)
    ):
        return HttpResponseForbidden(
            "No tienes permisos para modificar este requerimiento."
        )

    if requerimiento.estado.nombre not in [
        "Asignado",
        "En proceso",
    ]:
        messages.error(
            request,
            "No se pueden agregar observaciones en este estado."
        )
        return redirect("detalle_tecnico", pk=pk)

    if request.method == "POST":

        form = ObservacionRequerimientoForm(request.POST)

        if form.is_valid():

            HistorialRequerimiento.objects.create(
                requerimiento=requerimiento,
                usuario=request.user,
                estado_anterior=requerimiento.estado,
                estado_nuevo=requerimiento.estado,
                accion="Observación registrada",
                observacion=form.cleaned_data["observacion"],
            )

            messages.success(
                request,
                "Observación registrada correctamente."
            )

    return redirect("detalle_tecnico", pk=pk)

@login_required
@transaction.atomic
def resolver_requerimiento(request, pk):

    if request.method != "POST":
        return HttpResponseForbidden("Operación no permitida.")

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_for_update(),
        pk=pk,
    )

    if (
        requerimiento.responsable_id != request.user.id
        and not es_administrador(request.user)
    ):
        return HttpResponseForbidden(
            "No tienes permisos para resolver este requerimiento."
        )

    if requerimiento.estado.nombre != "En proceso":
        messages.error(
            request,
            "Solo se pueden resolver requerimientos en proceso."
        )
        return redirect("detalle_tecnico", pk=pk)

    form = ResolverRequerimientoForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Debes ingresar la solución aplicada."
        )
        return redirect("detalle_tecnico", pk=pk)

    estado_anterior = requerimiento.estado

    estado_resuelto = EstadoRequerimiento.objects.get(
        nombre="Resuelto"
    )

    solucion = form.cleaned_data["solucion"]

    requerimiento.estado = estado_resuelto
    requerimiento.solucion = solucion
    requerimiento.fecha_resolucion = timezone.now()

    requerimiento.save(
        update_fields=[
            "estado",
            "solucion",
            "fecha_resolucion",
            "updated_at",
        ]
    )

    HistorialRequerimiento.objects.create(
        requerimiento=requerimiento,
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_resuelto,
        accion="Requerimiento resuelto",
        observacion=solucion,
    )

    messages.success(
        request,
        "Requerimiento marcado como resuelto."
    )

    return redirect("detalle_tecnico", pk=pk) 

@login_required
@transaction.atomic
def cerrar_requerimiento(request, pk):

    if request.method != "POST":
        return HttpResponseForbidden("Operación no permitida.")

    requerimiento = get_object_or_404(
        Requerimiento.objects.select_for_update(),
        pk=pk,
    )

    if (
        requerimiento.responsable_id != request.user.id
        and not es_administrador(request.user)
    ):
        return HttpResponseForbidden(
            "No tienes permisos para cerrar este requerimiento."
        )

    if requerimiento.estado.nombre != "Resuelto":
        messages.error(
            request,
            "Solo se puede cerrar un requerimiento resuelto."
        )
        return redirect("detalle_tecnico", pk=pk)

    estado_anterior = requerimiento.estado

    estado_cerrado = EstadoRequerimiento.objects.get(
        nombre="Cerrado"
    )

    requerimiento.estado = estado_cerrado

    requerimiento.save(
        update_fields=[
            "estado",
            "updated_at",
        ]
    )

    HistorialRequerimiento.objects.create(
        requerimiento=requerimiento,
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_cerrado,
        accion="Requerimiento cerrado",
        observacion="El requerimiento fue cerrado.",
    )

    messages.success(
        request,
        "Requerimiento cerrado correctamente."
    )

    return redirect("detalle_tecnico", pk=pk)

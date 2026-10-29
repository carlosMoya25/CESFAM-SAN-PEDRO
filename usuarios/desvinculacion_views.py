from core.auditoria import marcar_formulario, marcar_rechazo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .desvinculacion import desactivar_usuario, pendientes_usuario
from .forms import DesvinculacionForm
from .models import Usuario
from .utils import es_administrador


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def desvincular_usuario(request, pk):
    if not es_administrador(request.user):
        return HttpResponseForbidden()
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk or not usuario.is_active:
        marcar_rechazo()
        messages.error(request, "Selecciona otra cuenta activa para desactivar.")
        return redirect("usuarios:detalle_usuario", pk=pk)
    pendientes = pendientes_usuario(usuario).select_related("estado")
    form = DesvinculacionForm(request.POST if request.method == "POST" else None,
                             usuario=usuario, tiene_pendientes=pendientes.exists())
    if request.method == "POST" and form.is_valid():
        try:
            reemplazo = form.cleaned_data["reemplazo"]
            cantidad = desactivar_usuario(administrador=request.user, usuario_id=pk,
                                          reemplazo_id=reemplazo.pk if reemplazo else None,
                                          motivo=form.cleaned_data["motivo"])
        except ValidationError as exc:
            marcar_rechazo()
            form.add_error(None, exc)
        else:
            messages.success(request, f"Cuenta desactivada y sesiones revocadas. Solicitudes reasignadas: {cantidad}.")
            return redirect("usuarios:detalle_usuario", pk=pk)
    marcar_formulario(form)
    return render(request, "usuarios/administracion/desvincular.html",
                  {"usuario_detalle": usuario, "form": form, "pendientes": pendientes})

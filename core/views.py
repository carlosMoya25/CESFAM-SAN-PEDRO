from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    usuario = request.user

    roles = list(
        usuario.groups.values_list("name", flat=True)
    )

    contexto = {
        "usuario": usuario,
        "roles": roles,
    }

    return render(
        request,
        "core/dashboard.html",
        contexto
    )
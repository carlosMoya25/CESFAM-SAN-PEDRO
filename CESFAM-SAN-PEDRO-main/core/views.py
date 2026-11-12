from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from inventario.models import StockAnexo
from usuarios.utils import es_administrador, es_tecnico, puede_gestionar_farmacia

from .reportes import datos_farmacia, datos_insumos, datos_requerimientos
from .reportes_forms import FiltroReporteForm


@login_required
def dashboard(request):
    grupos = list(
        request.user.groups.values_list("name", flat=True)
    )

    form = FiltroReporteForm(request.GET or None)
    desde, hasta = form.rango()
    ubicacion = form.ubicacion_seleccionada()

    # REQUERIMIENTOS e INSUMOS: visibles para cualquier usuario autenticado,
    # igual que en el dashboard original.
    ti = datos_requerimientos(desde, hasta, ubicacion)
    insumos = datos_insumos(desde, hasta, ubicacion)

    # FARMACIA: se mantiene restringido a quien puede gestionar farmacia.
    farmacia = None
    stock_medicamentos_sin_lote = False
    if puede_gestionar_farmacia(request.user):
        farmacia = datos_farmacia(desde, hasta, ubicacion)
        stock_medicamentos_sin_lote = StockAnexo.objects.filter(
            articulo__medicamento__isnull=False, cantidad__gt=0
        ).exists()

    context = {
        "grupos": grupos,
        "form": form,
        "desde": desde,
        "hasta": hasta,
        "ubicacion": ubicacion,
        "puede_ti": es_tecnico(request.user) or es_administrador(request.user),
        "ti": ti,
        "insumos": insumos,
        "farmacia": farmacia,
        "stock_medicamentos_sin_lote": stock_medicamentos_sin_lote,
    }

    return render(
        request,
        "core/dashboard.html",
        context
    )

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from requerimientos.models import Requerimiento
from inventario.models import Articulo, StockAnexo


@login_required
def dashboard(request):
    #grupos

    grupos = list(
    request.user.groups.values_list(
        "name",
        flat=True
    )
)

    # ==========================
    # REQUERIMIENTOS
    # ==========================

    total_requerimientos = Requerimiento.objects.count()

    pendientes = Requerimiento.objects.filter(
        estado__nombre__iexact="Pendiente"
    ).count()

    en_proceso = Requerimiento.objects.filter(
        estado__nombre__iexact="En proceso"
    ).count()

    resueltos = Requerimiento.objects.filter(
        estado__nombre__iexact="Resuelto"
    ).count()


    # ==========================
    # INVENTARIO
    # ==========================

    total_articulos = Articulo.objects.filter(
        activo=True
    ).count()

    stocks = StockAnexo.objects.select_related(
        "articulo",
        "anexo"
    )

    stock_bajo = sum(
        1
        for stock in stocks
        if stock.cantidad <= stock.articulo.stock_minimo
    )


    context = {
        "grupos": grupos,
        "total_requerimientos": total_requerimientos,
        "pendientes": pendientes,
        "en_proceso": en_proceso,
        "resueltos": resueltos,

        "total_articulos": total_articulos,
        "stock_bajo": stock_bajo,
    }

    return render(
        request,
        "core/dashboard.html",
        context
    )
from django.shortcuts import get_object_or_404
from inventario.forms import ArticuloForm
from inventario.forms import CategoriaArticuloForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.db.models import Sum, F

from usuarios.utils import puede_gestionar_inventario

from .forms import (
    AjusteInventarioForm,
    EntradaInventarioForm,
    SalidaInventarioForm,
    TransferenciaInventarioForm,
    CategoriaArticulo,
    Articulo,
)
from .models import MovimientoInventario, StockAnexo, CategoriaArticulo, Articulo
from .services import (
    registrar_ajuste,
    registrar_entrada,
    registrar_salida,
    registrar_transferencia,
)



def validar_acceso_inventario(usuario):
    return puede_gestionar_inventario(usuario)



@login_required
def panel_inventario(request):

    # Validación de permisos
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder al inventario."
        )

    # ==========================================
    # STOCK ACTUAL
    # ==========================================

    stocks = (
        StockAnexo.objects
        .select_related(
            "articulo",
            "articulo__categoria",
            "anexo"
        )
        .order_by("articulo__nombre", "anexo__nombre")
    )

    # consulta de stock


    # ==========================================
    # ÚLTIMOS MOVIMIENTOS
    # ==========================================

    movimientos = (
        MovimientoInventario.objects
        .select_related(
            "tipo_movimiento",
            "anexo_origen",
            "anexo_destino",
            "usuario"
        )
        .prefetch_related("detalles__articulo")
        .order_by("-fecha")[:10]
    )

    # ==========================================
    # INDICADORES DEL DASHBOARD
    # ==========================================

    # Total de artículos registrados
    total_articulos = Articulo.objects.count()

    # Total de categorías
    total_categorias = CategoriaArticulo.objects.count()

    # Total de unidades en inventario
    total_unidades = (
        StockAnexo.objects.aggregate(
            total=Sum("cantidad")
        )["total"] or 0
    )

    # Registros de stock bajo o igual al mínimo
    total_stock_bajo = (
        StockAnexo.objects
        .filter(
            cantidad__lte=F("articulo__stock_minimo")
        )
        .count()
    )

    # Total de movimientos registrados
    total_movimientos = MovimientoInventario.objects.count()

    # ==========================================
    # CONTEXTO
    # ==========================================

    context = {
        "stocks": stocks,
        "movimientos": movimientos,

        "total_articulos": total_articulos,
        "total_categorias": total_categorias,
        "total_unidades": total_unidades,
        "total_stock_bajo": total_stock_bajo,
        "total_movimientos": total_movimientos,
    }

    return render(
        request,
        "inventario/panel.html",
        context
    )



@login_required
def consultar_stock(request):

    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para consultar el inventario."
        )

    # Filtros enviados mediante GET
    busqueda = request.GET.get("buscar", "").strip()
    anexo_id = request.GET.get("anexo", "")
    categoria_id = request.GET.get("categoria", "")
    estado = request.GET.get("estado", "")

    # Consultar existencias
    stocks = (
        StockAnexo.objects
        .select_related(
            "articulo",
            "articulo__categoria",
            "anexo"
        )
    )

    if busqueda:
        stocks = stocks.filter(
            articulo__nombre__icontains=busqueda
        )

    if anexo_id.isdigit():
        stocks = stocks.filter(anexo_id=int(anexo_id))

    if categoria_id.isdigit():
        stocks = stocks.filter(
            articulo__categoria_id=int(categoria_id)
        )

    if estado == "agotado":
        stocks = stocks.filter(cantidad=0)

    elif estado == "bajo":
        stocks = stocks.filter(
            cantidad__gt=0,
            cantidad__lte=F("articulo__stock_minimo")
        )

    elif estado == "disponible":
        stocks = stocks.filter(
            cantidad__gt=F("articulo__stock_minimo")
        )

    stocks = stocks.order_by(
        "articulo__nombre",
        "anexo__nombre"
    )

    # Indicadores correspondientes a los filtros
    resumen = stocks.aggregate(
        total_unidades=Sum("cantidad")
    )

    total_unidades = resumen["total_unidades"] or 0

    total_registros = stocks.count()

    total_agotados = stocks.filter(
        cantidad=0
    ).count()

    total_stock_bajo = stocks.filter(
        cantidad__gt=0,
        cantidad__lte=F("articulo__stock_minimo")
    ).count()

    # Obtener anexos existentes desde StockAnexo
    # para evitar depender del nombre de su modelo.
    Anexo = StockAnexo._meta.get_field(
        "anexo"
    ).remote_field.model

    anexos = Anexo.objects.all().order_by("nombre")

    categorias = CategoriaArticulo.objects.all().order_by(
        "nombre"
    )

    context = {
        "stocks": stocks,
        "anexos": anexos,
        "categorias": categorias,
        "busqueda": busqueda,
        "anexo_seleccionado": anexo_id,
        "categoria_seleccionada": categoria_id,
        "estado_seleccionado": estado,
        "total_registros": total_registros,
        "total_unidades": total_unidades,
        "total_agotados": total_agotados,
        "total_stock_bajo": total_stock_bajo,
    }

    return render(
        request,
        "inventario/consultar_stock.html",
        context
    )



@login_required
def entrada_inventario(request):
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden("No tienes permisos.")

    if request.method == "POST":
        form = EntradaInventarioForm(request.POST)

        if form.is_valid():
            try:
                registrar_entrada(
                    usuario=request.user,
                    anexo=form.cleaned_data["anexo"],
                    articulo=form.cleaned_data["articulo"],
                    cantidad=form.cleaned_data["cantidad"],
                    motivo=form.cleaned_data["motivo"],
                )

                messages.success(
                    request,
                    "Entrada de inventario registrada correctamente.",
                )
                return redirect("inventario:panel")

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = EntradaInventarioForm()

    return render(
        request,
        "inventario/movimiento_form.html",
        {
            "form": form,
            "titulo": "Registrar entrada",
        },
    )


@login_required
def salida_inventario(request):
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden("No tienes permisos.")

    if request.method == "POST":
        form = SalidaInventarioForm(request.POST)

        if form.is_valid():
            try:
                registrar_salida(
                    usuario=request.user,
                    anexo=form.cleaned_data["anexo"],
                    articulo=form.cleaned_data["articulo"],
                    cantidad=form.cleaned_data["cantidad"],
                    motivo=form.cleaned_data["motivo"],
                )

                messages.success(
                    request,
                    "Salida de inventario registrada correctamente.",
                )
                return redirect("inventario:panel")

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = SalidaInventarioForm()

    return render(
        request,
        "inventario/movimiento_form.html",
        {
            "form": form,
            "titulo": "Registrar salida",
        },
    )


@login_required
def transferencia_inventario(request):
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden("No tienes permisos.")

    if request.method == "POST":
        form = TransferenciaInventarioForm(request.POST)

        if form.is_valid():
            try:
                registrar_transferencia(
                    usuario=request.user,
                    anexo_origen=form.cleaned_data["anexo_origen"],
                    anexo_destino=form.cleaned_data["anexo_destino"],
                    articulo=form.cleaned_data["articulo"],
                    cantidad=form.cleaned_data["cantidad"],
                    motivo=form.cleaned_data["motivo"],
                )

                messages.success(
                    request,
                    "Transferencia registrada correctamente.",
                )
                return redirect("inventario:panel")

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = TransferenciaInventarioForm()

    return render(
        request,
        "inventario/movimiento_form.html",
        {
            "form": form,
            "titulo": "Transferir inventario",
        },
    )


@login_required
def historial_movimientos(request):
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden("No tienes permisos.")

    movimientos = (
        MovimientoInventario.objects
        .select_related(
            "tipo_movimiento",
            "anexo_origen",
            "anexo_destino",
            "usuario",
        )
        .prefetch_related("detalles__articulo")
        .order_by("-fecha")
    )

    return render(
        request,
        "inventario/historial.html",
        {
            "movimientos": movimientos,
        },
    )

@login_required
def ajuste_inventario(request):
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden("No tienes permisos.")

    if request.method == "POST":
        form = AjusteInventarioForm(request.POST)

        if form.is_valid():
            try:
                registrar_ajuste(
                    usuario=request.user,
                    anexo=form.cleaned_data["anexo"],
                    articulo=form.cleaned_data["articulo"],
                    cantidad=form.cleaned_data["cantidad"],
                    tipo_ajuste=form.cleaned_data["tipo_ajuste"],
                    motivo=form.cleaned_data["motivo"],
                )

                messages.success(
                    request,
                    "Ajuste de inventario registrado correctamente.",
                )

                return redirect("inventario:panel")

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = AjusteInventarioForm()

    return render(
        request,
        "inventario/movimiento_form.html",
        {
            "form": form,
            "titulo": "Ajustar inventario",
        },
    )

@login_required
def categorias(request):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    categorias = CategoriaArticulo.objects.all().order_by("nombre")

    return render(
        request,
        "inventario/categorias.html",
        {"categorias": categorias},
    )


@login_required
def crear_categoria(request):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    if request.method == "POST":
        form = CategoriaArticuloForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Categoría creada correctamente.")
            return redirect("inventario:categorias")
    else:
        form = CategoriaArticuloForm()

    return render(
        request,
        "inventario/categoria_form.html",
        {
            "form": form,
            "titulo": "Nueva categoría",
        },
    )


@login_required
def editar_categoria(request, pk):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    categoria = get_object_or_404(CategoriaArticulo, pk=pk)

    if request.method == "POST":
        form = CategoriaArticuloForm(request.POST, instance=categoria)

        if form.is_valid():
            form.save()
            messages.success(request, "Categoría actualizada correctamente.")
            return redirect("inventario:categorias")
    else:
        form = CategoriaArticuloForm(instance=categoria)

    return render(
        request,
        "inventario/categoria_form.html",
        {
            "form": form,
            "titulo": "Editar categoría",
            "categoria": categoria,
        },
    )


@login_required
def articulos(request):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    articulos = (
        Articulo.objects
        .select_related("categoria")
        .all()
        .order_by("nombre")
    )

    return render(
        request,
        "inventario/articulos.html",
        {"articulos": articulos},
    )


@login_required
def crear_articulo(request):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    if request.method == "POST":
        form = ArticuloForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Artículo creado correctamente.")
            return redirect("inventario:articulos")
    else:
        form = ArticuloForm()

    return render(
        request,
        "inventario/articulo_form.html",
        {
            "form": form,
            "titulo": "Nuevo artículo",
        },
    )


@login_required
def editar_articulo(request, pk):
    if not puede_gestionar_inventario(request.user):
        messages.error(request, "No tienes permisos para administrar el inventario.")
        return redirect("dashboard")

    articulo = get_object_or_404(Articulo, pk=pk)

    if request.method == "POST":
        form = ArticuloForm(request.POST, instance=articulo)

        if form.is_valid():
            form.save()
            messages.success(request, "Artículo actualizado correctamente.")
            return redirect("inventario:articulos")
    else:
        form = ArticuloForm(instance=articulo)

    return render(
        request,
        "inventario/articulo_form.html",
        {
            "form": form,
            "titulo": "Editar artículo",
            "articulo": articulo,
        },
    )
from django.shortcuts import get_object_or_404
from inventario.forms import ArticuloForm
from inventario.forms import CategoriaArticuloForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

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
    if not validar_acceso_inventario(request.user):
        return HttpResponseForbidden(
            "No tienes permisos para acceder al inventario."
        )

    stocks = (
        StockAnexo.objects
        .select_related("articulo", "articulo__categoria", "anexo")
        .order_by("articulo__nombre", "anexo__nombre")
    )

    movimientos = (
        MovimientoInventario.objects
        .select_related(
            "tipo_movimiento",
            "anexo_origen",
            "anexo_destino",
            "usuario",
        )
        .prefetch_related("detalles__articulo")
        .order_by("-fecha")[:10]
    )

    return render(
        request,
        "inventario/panel.html",
        {
            "stocks": stocks,
            "movimientos": movimientos,
        },
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

from farmacia.models import MovimientoFarmacia
from datetime import timedelta
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from .forms import IngresoMedicamentoForm
from .services import registrar_entrada_medicamento
from .models import Medicamento, StockLote
from .forms import MedicamentoForm
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.shortcuts import get_object_or_404



@login_required
def dashboard(request):

    hoy = timezone.localdate()
    fecha_limite = hoy + timedelta(days=30)

    total_medicamentos = Medicamento.objects.filter(
        activo=True
    ).count()

    total_stock = (
        StockLote.objects.aggregate(
            total=Sum("cantidad")
        )["total"] or 0
    )

    lotes_proximos = (
        StockLote.objects.filter(
            cantidad__gt=0,
            lote__activo=True,
            lote__fecha_vencimiento__gte=hoy,
            lote__fecha_vencimiento__lte=fecha_limite,
        )
        .select_related(
            "lote__medicamento__articulo",
            "anexo",
        )
        .order_by("lote__fecha_vencimiento")[:10]
    )

    lotes_vencidos = StockLote.objects.filter(
        cantidad__gt=0,
        lote__fecha_vencimiento__lt=hoy,
    ).count()

    movimientos_recientes = (
        MovimientoFarmacia.objects
        .select_related(
            "usuario",
            "anexo_origen",
            "anexo_destino",
        )
        .order_by("-fecha")[:10]
    )

    total_movimientos = MovimientoFarmacia.objects.count()

    contexto = {
        "total_medicamentos": total_medicamentos,
        "total_stock": total_stock,
        "lotes_proximos": lotes_proximos,
        "lotes_vencidos": lotes_vencidos,
        "movimientos_recientes": movimientos_recientes,
        "total_movimientos": total_movimientos,
    }

    return render(
        request,
        "farmacia/dashboard.html",
        contexto,
    )


def puede_administrar_farmacia(usuario):
    return usuario.is_authenticated and usuario.is_active and usuario.is_superuser


@login_required
@user_passes_test(puede_administrar_farmacia)
def lista_medicamentos(request):
    busqueda = request.GET.get("q", "").strip()

    medicamentos = Medicamento.objects.select_related(
        "articulo"
    ).annotate(
        stock_total=Sum("lotes__stocks__cantidad")
    )

    if busqueda:
        from django.db.models import Q

        medicamentos = medicamentos.filter(
            Q(articulo__nombre__icontains=busqueda) |
            Q(principio_activo__icontains=busqueda) |
            Q(articulo__codigo__icontains=busqueda)
        )

    return render(
        request,
        "farmacia/medicamentos_lista.html",
        {
            "medicamentos": medicamentos,
            "busqueda": busqueda,
        },
    )


@login_required
@user_passes_test(puede_administrar_farmacia)
def crear_medicamento(request):
    form = MedicamentoForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():
        medicamento = form.save()

        messages.success(
            request,
            "Medicamento registrado correctamente."
        )

        return redirect(
            "farmacia:detalle_medicamento",
            pk=medicamento.pk,
        )

    return render(
        request,
        "farmacia/medicamento_form.html",
        {
            "form": form,
            "titulo": "Registrar medicamento",
        },
    )


@login_required
@user_passes_test(puede_administrar_farmacia)
def editar_medicamento(request, pk):
    medicamento = get_object_or_404(
        Medicamento,
        pk=pk,
    )

    form = MedicamentoForm(
        request.POST or None,
        medicamento=medicamento,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(
            request,
            "Medicamento actualizado correctamente."
        )

        return redirect(
            "farmacia:detalle_medicamento",
            pk=medicamento.pk,
        )

    return render(
        request,
        "farmacia/medicamento_form.html",
        {
            "form": form,
            "titulo": "Editar medicamento",
        },
    )


@login_required
@user_passes_test(puede_administrar_farmacia)
def detalle_medicamento(request, pk):
    medicamento = get_object_or_404(
        Medicamento.objects.select_related("articulo"),
        pk=pk,
    )

    stocks = StockLote.objects.filter(
        lote__medicamento=medicamento,
    ).select_related(
        "anexo",
        "lote",
    ).order_by(
        "anexo__nombre",
        "lote__fecha_vencimiento",
    )

    return render(
        request,
        "farmacia/medicamento_detalle.html",
        {
            "medicamento": medicamento,
            "stocks": stocks,
            "stock_total": sum(s.cantidad for s in stocks),
        },
    )


@login_required
@user_passes_test(puede_administrar_farmacia)
@require_POST
def cambiar_estado_medicamento(request, pk):
    medicamento = get_object_or_404(
        Medicamento,
        pk=pk,
    )

    medicamento.activo = not medicamento.activo
    medicamento.save(update_fields=["activo", "updated_at"])

    messages.success(
        request,
        "Estado del medicamento actualizado."
    )

    return redirect("farmacia:lista_medicamentos")



@login_required
def registrar_entrada(request):

    if request.method == "POST":
        form = IngresoMedicamentoForm(request.POST)

        if form.is_valid():
            datos = form.cleaned_data

            try:
                movimiento = registrar_entrada_medicamento(
                    medicamento=datos["medicamento"],
                    anexo=datos["anexo"],
                    numero_lote=datos["numero_lote"],
                    fecha_vencimiento=datos["fecha_vencimiento"],
                    cantidad=datos["cantidad"],
                    usuario=request.user,
                    motivo=datos["motivo"],
                )

                messages.success(
                    request,
                    f"Ingreso registrado correctamente. "
                    f"Movimiento #{movimiento.pk}",
                )

                return redirect("farmacia:dashboard")

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = IngresoMedicamentoForm()

    return render(
        request,
        "farmacia/registrar_entrada.html",
        {"form": form},
    )



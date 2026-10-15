
from django.db import models
from django.core.validators import MinValueValidator


class Medicamento(models.Model):

    articulo = models.OneToOneField(
        "inventario.Articulo",
        on_delete=models.PROTECT,
        related_name="medicamento",
    )

    principio_activo = models.CharField(
        max_length=150
    )

    concentracion = models.CharField(
        max_length=100
    )

    forma_farmaceutica = models.CharField(
        max_length=100
    )

    presentacion = models.CharField(
        max_length=150,
        blank=True
    )

    requiere_receta = models.BooleanField(
        default=True
    )

    activo = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"
        ordering = ["articulo__nombre"]

    def __str__(self):
        return self.articulo.nombre


class LoteMedicamento(models.Model):

    medicamento = models.ForeignKey(
        Medicamento,
        on_delete=models.PROTECT,
        related_name="lotes",
    )

    numero_lote = models.CharField(
        max_length=100
    )

    fecha_vencimiento = models.DateField()

    activo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Lote de medicamento"
        verbose_name_plural = "Lotes de medicamentos"

        constraints = [
            models.UniqueConstraint(
                fields=["medicamento", "numero_lote"],
                name="unique_lote_medicamento",
            )
        ]

    def __str__(self):
        return (
            f"{self.medicamento} - "
            f"Lote {self.numero_lote}"
        )


class StockLote(models.Model):

    lote = models.ForeignKey(
        LoteMedicamento,
        on_delete=models.PROTECT,
        related_name="stocks",
    )

    anexo = models.ForeignKey(
        "organizacion.Anexo",
        on_delete=models.PROTECT,
        related_name="stocks_lotes",
    )

    cantidad = models.PositiveIntegerField(
        default=0
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Stock por lote"
        verbose_name_plural = "Stock por lotes"

        constraints = [
            models.UniqueConstraint(
                fields=["lote", "anexo"],
                name="unique_stock_lote_anexo",
            )
        ]

    def __str__(self):
        return (
            f"{self.lote} - "
            f"{self.anexo}: {self.cantidad}"
        )



from django.conf import settings


class MovimientoFarmacia(models.Model):

    TIPOS_MOVIMIENTO = [
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("TRANSFERENCIA", "Transferencia"),
        ("ENTREGA", "Entrega a paciente"),
        ("AJUSTE", "Ajuste de inventario"),
    ]

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_MOVIMIENTO,
    )

    anexo_origen = models.ForeignKey(
        "organizacion.Anexo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_farmacia_salida",
    )

    anexo_destino = models.ForeignKey(
        "organizacion.Anexo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_farmacia_entrada",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_farmacia",
    )

    motivo = models.TextField(blank=True)

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de farmacia"
        verbose_name_plural = "Movimientos de farmacia"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.fecha:%d/%m/%Y %H:%M}"


class DetalleMovimientoFarmacia(models.Model):

    movimiento = models.ForeignKey(
        MovimientoFarmacia,
        on_delete=models.PROTECT,
        related_name="detalles",
    )

    lote = models.ForeignKey(
        "farmacia.LoteMedicamento",
        on_delete=models.PROTECT,
        related_name="movimientos_farmacia",
    )

    cantidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "Detalle de movimiento de farmacia"
        verbose_name_plural = "Detalles de movimientos de farmacia"

    def __str__(self):
        return f"{self.lote} x {self.cantidad}"

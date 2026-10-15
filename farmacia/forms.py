
from datetime import date

from django import forms

from organizacion.models import Anexo
from .models import Medicamento


class IngresoMedicamentoForm(forms.Form):

    medicamento = forms.ModelChoiceField(
        queryset=Medicamento.objects.none(),
        label="Medicamento",
        empty_label="Seleccione un medicamento",
    )

    anexo = forms.ModelChoiceField(
        queryset=Anexo.objects.none(),
        label="Ubicación de destino",
        empty_label="Seleccione una ubicación",
    )

    numero_lote = forms.CharField(
        max_length=100,
        label="Número de lote",
    )

    fecha_vencimiento = forms.DateField(
        label="Fecha de vencimiento",
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
    )

    cantidad = forms.IntegerField(
        label="Cantidad recibida",
        min_value=1,
    )

    motivo = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["medicamento"].queryset = (
            Medicamento.objects.filter(
                activo=True,
                articulo__activo=True,
            ).select_related("articulo")
        )

        self.fields["anexo"].queryset = (
            Anexo.objects.filter(activo=True)
        )

    def clean_numero_lote(self):
        numero = self.cleaned_data["numero_lote"].strip()

        if not numero:
            raise forms.ValidationError(
                "Debe ingresar un número de lote."
            )

        return numero

    def clean_fecha_vencimiento(self):
        fecha = self.cleaned_data["fecha_vencimiento"]

        if fecha < date.today():
            raise forms.ValidationError(
                "No se permite ingresar medicamentos vencidos."
            )

        return fecha


from django.db import transaction

from inventario.models import Articulo, CategoriaArticulo
from .models import Medicamento


class MedicamentoForm(forms.Form):

    nombre = forms.CharField(
        max_length=150,
        label="Nombre del medicamento",
    )

    codigo = forms.CharField(
        max_length=50,
        label="Código interno",
        required=False,
    )

    descripcion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    principio_activo = forms.CharField(
        max_length=150,
    )

    concentracion = forms.CharField(
        max_length=100,
    )

    forma_farmaceutica = forms.CharField(
        max_length=100,
    )

    presentacion = forms.CharField(
        max_length=150,
        required=False,
    )

    stock_minimo = forms.IntegerField(
        min_value=0,
        initial=0,
    )

    requiere_receta = forms.BooleanField(
        required=False,
        initial=True,
    )

    def __init__(self, *args, medicamento=None, **kwargs):
        self.medicamento = medicamento
        super().__init__(*args, **kwargs)

        if medicamento and not self.is_bound:
            articulo = medicamento.articulo

            self.initial.update({
                "nombre": articulo.nombre,
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "principio_activo": medicamento.principio_activo,
                "concentracion": medicamento.concentracion,
                "forma_farmaceutica": medicamento.forma_farmaceutica,
                "presentacion": medicamento.presentacion,
                "stock_minimo": articulo.stock_minimo,
                "requiere_receta": medicamento.requiere_receta,
            })

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip() or None

        existentes = Articulo.objects.filter(codigo=codigo)

        if self.medicamento:
            existentes = existentes.exclude(
                pk=self.medicamento.articulo_id
            )

        if codigo and existentes.exists():
            raise forms.ValidationError(
                "Ya existe un artículo con este código."
            )

        return codigo

    @transaction.atomic
    def save(self):
        datos = self.cleaned_data

        categoria, _ = CategoriaArticulo.objects.get_or_create(
            nombre="Medicamentos",
            defaults={
                "descripcion": "Catálogo de medicamentos de Farmacia",
            },
        )

        if self.medicamento:
            medicamento = Medicamento.objects.select_for_update().get(
                pk=self.medicamento.pk
            )
            articulo = Articulo.objects.select_for_update().get(
                pk=medicamento.articulo_id
            )
        else:
            articulo = Articulo()
            medicamento = Medicamento(articulo=articulo)

        articulo.nombre = datos["nombre"]
        articulo.codigo = datos["codigo"]
        articulo.descripcion = datos["descripcion"]
        articulo.categoria = categoria
        articulo.stock_minimo = datos["stock_minimo"]
        articulo.save()

        medicamento.articulo = articulo
        medicamento.principio_activo = datos["principio_activo"]
        medicamento.concentracion = datos["concentracion"]
        medicamento.forma_farmaceutica = datos["forma_farmaceutica"]
        medicamento.presentacion = datos["presentacion"]
        medicamento.requiere_receta = datos["requiere_receta"]
        medicamento.save()

        return medicamento

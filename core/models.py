from django.db import models

from django.conf import settings
import uuid


class PoliticaRespaldos(models.Model):
    class Frecuencia(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Sin definir"
        MANUAL = "MANUAL", "Manual, según procedimiento"
        DIARIA = "DIARIA", "Diariamente"
        DOCE_HORAS = "DOCE_HORAS", "Cada 12 horas"
        SEMANAL = "SEMANAL", "Semanalmente"

    class Ubicacion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Por confirmar"
        MISMA = "MISMA", "En la misma ubicación física"
        OTRA = "OTRA", "En otra ubicación física"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    frecuencia = models.CharField(max_length=20, choices=Frecuencia.choices, default=Frecuencia.PENDIENTE)
    hora = models.TimeField(null=True, blank=True)
    dia_semana = models.PositiveSmallIntegerField(null=True, blank=True)
    copias_diarias = models.PositiveSmallIntegerField(null=True, blank=True)
    copias_semanales = models.PositiveSmallIntegerField(null=True, blank=True)
    copias_mensuales = models.PositiveSmallIntegerField(null=True, blank=True)
    prueba_cada_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    custodio = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="custodia_claves_respaldos")
    suplente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="suplencias_claves_respaldos")
    procedimiento_clave = models.CharField(max_length=1000, blank=True)
    ubicacion = models.CharField(max_length=20, choices=Ubicacion.choices, default=Ubicacion.PENDIENTE)
    proteccion_adicional = models.CharField(max_length=1500, blank=True)
    revision = models.PositiveIntegerField(default=0)
    actualizada_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="politica_respaldos_unica"),
            models.CheckConstraint(condition=models.Q(dia_semana__isnull=True) | models.Q(dia_semana__lte=6),
                                   name="politica_respaldos_dia_valido"),
            models.CheckConstraint(condition=models.Q(custodio__isnull=True) | models.Q(suplente__isnull=True) |
                                   ~models.Q(custodio=models.F("suplente")), name="politica_respaldos_custodios_distintos"),
        ]


class CambioPoliticaRespaldos(models.Model):
    politica = models.ForeignKey(PoliticaRespaldos, on_delete=models.PROTECT, related_name="cambios")
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      related_name="cambios_politica_respaldos")
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=1000)
    antes = models.JSONField(default=dict)
    despues = models.JSONField(default=dict)

    class Meta:
        ordering = ["-fecha", "-pk"]


class ProgramacionRespaldos(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    activa = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    politica_revision = models.PositiveIntegerField(default=0)
    activada_at = models.DateTimeField(null=True, blank=True)
    ejecutor = models.CharField(max_length=80, blank=True)
    ultimo_latido = models.DateTimeField(null=True, blank=True)
    listo = models.BooleanField(default=False)
    diagnostico = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="programacion_respaldos_unica")]


class CambioProgramacionRespaldos(models.Model):
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      related_name="cambios_programacion_respaldos")
    fecha = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField()
    politica_revision = models.PositiveIntegerField()
    motivo = models.CharField(max_length=1000)

    class Meta:
        ordering = ["-fecha", "-pk"]


class EjecucionProgramadaRespaldo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ejecutor = models.CharField(max_length=80)
    politica_revision = models.PositiveIntegerField()
    programada_para = models.DateTimeField()
    iniciada_at = models.DateTimeField(auto_now_add=True)
    finalizada_at = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=[("EN_CURSO", "En curso"), ("CORRECTA", "Copia creada"),
                               ("FALLIDA", "Fallida"), ("INTERRUMPIDA", "Interrumpida")], default="EN_CURSO")
    respaldo = models.ForeignKey("RespaldoBase", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="ejecuciones_programadas")
    detalle = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-iniciada_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["politica_revision", "programada_para"], name="respaldo_turno_unico")]


class RespaldoBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creado_at = models.DateTimeField(auto_now_add=True)
    motor = models.CharField(max_length=20)
    version_origen = models.CharField(max_length=120)
    tamano = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    verificado_at = models.DateTimeField(null=True, blank=True)
    verificacion = models.JSONField(default=dict)

    class Meta:
        ordering = ["-creado_at"]


class DescargaRespaldo(models.Model):
    respaldo = models.ForeignKey(RespaldoBase, on_delete=models.PROTECT, related_name="descargas")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="descargas_respaldos")
    fecha = models.DateTimeField(auto_now_add=True)
    sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ["-fecha", "-pk"]


class PruebaRestauracion(models.Model):
    respaldo = models.ForeignKey(RespaldoBase, on_delete=models.PROTECT, related_name="pruebas")
    fecha = models.DateTimeField(auto_now_add=True)
    correcta = models.BooleanField(default=False)
    detalle = models.JSONField(default=dict)

    class Meta:
        ordering = ["-fecha", "-pk"]


class ReglaConservacion(models.Model):
    class Categoria(models.TextChoices):
        BORRADORES = "BORRADORES", "Borradores de derechos"
        DERECHOS = "DERECHOS", "Solicitudes de derechos respondidas"
        IMPORTACIONES = "IMPORTACIONES", "Importaciones pendientes de farmacia"
        SESIONES = "SESIONES", "Sesiones vencidas"
        REQUERIMIENTOS = "REQUERIMIENTOS", "Requerimientos TI cerrados o cancelados"
        CONSTANCIAS = "CONSTANCIAS", "Constancias de avisos anteriores"
        CUENTAS = "CUENTAS", "Cuentas inactivas"

    categoria = models.CharField(max_length=30, choices=Categoria.choices, unique=True)
    dias = models.PositiveIntegerField(null=True, blank=True)
    fundamento = models.CharField(max_length=1000, blank=True)
    revision = models.PositiveIntegerField(default=0)
    actualizada_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(dias__isnull=True) | models.Q(dias__gte=1),
                                              name="conservacion_dias_positivos")]


class CambioReglaConservacion(models.Model):
    regla = models.ForeignKey(ReglaConservacion, on_delete=models.PROTECT, related_name="historial")
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="cambios_conservacion")
    anterior = models.JSONField(default=dict)
    nuevo = models.JSONField(default=dict)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class SimulacionConservacion(models.Model):
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="simulaciones_conservacion")
    resultado = models.JSONField(default=dict)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class SolicitudDerecho(models.Model):
    class Tipo(models.TextChoices):
        ACCESO = "ACCESO", "Acceso a mis datos"
        RECTIFICACION = "RECTIFICACION", "Rectificación de mis datos"

    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="solicitudes_derechos")
    clave_creacion = models.UUIDField(default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    detalle = models.TextField(max_length=2000)
    campo_rectificar = models.CharField(max_length=100, blank=True)
    valor_solicitado = models.CharField(max_length=250, blank=True)
    estado = models.CharField(max_length=20, default="BORRADOR", choices=[
        ("BORRADOR", "Borrador · sin enviar"), ("RECIBIDA", "Recibida"), ("RESPONDIDA", "Respondida")])
    enviada_at = models.DateTimeField(null=True, blank=True)
    fecha_limite = models.DateField(null=True, blank=True)
    recepcion = models.JSONField(default=dict, blank=True)
    respuesta = models.TextField(max_length=10000, blank=True)
    respondida_at = models.DateTimeField(null=True, blank=True)
    respondida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      null=True, blank=True, related_name="derechos_respondidos")
    verificacion_identidad = models.CharField(max_length=500, blank=True)
    revision = models.PositiveIntegerField(default=1)
    creada_at = models.DateTimeField(auto_now_add=True)
    actualizada_at = models.DateTimeField(auto_now=True)

    @property
    def folio(self):
        prefijo = "B" if self.estado == "BORRADOR" else "R"
        return f"PRIV-{prefijo}-{self.pk:06d}"

    class Meta:
        ordering = ["-actualizada_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["solicitante", "clave_creacion"],
                                               name="derecho_creacion_unica")]


class EventoSolicitudDerecho(models.Model):
    solicitud = models.ForeignKey(SolicitudDerecho, on_delete=models.PROTECT, related_name="historial")
    accion = models.CharField(max_length=30, choices=[("CREADA", "Borrador creado"), ("EDITADA", "Borrador actualizado"),
                                                    ("ENVIADA", "Solicitud recibida"), ("RESPONDIDA", "Respuesta registrada")])
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name="eventos_derechos")
    revision = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class ConfiguracionPrivacidad(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name="encargos_privacidad")
    revision = models.PositiveIntegerField(default=0)
    entidad = models.CharField(max_length=200, blank=True)
    contacto = models.EmailField(blank=True)
    validador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="validaciones_privacidad_asignadas")
    autorizados = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="canales_privacidad_autorizados")
    contacto_validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name="contactos_privacidad_validados")
    contacto_validado_at = models.DateTimeField(null=True, blank=True)
    evidencia_validacion = models.CharField(max_length=500, blank=True)
    canal_habilitado = models.BooleanField(default=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="privacidad_configuracion_unica")]


class HistorialCanalPrivacidad(models.Model):
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="cambios_canal_privacidad")
    accion = models.CharField(max_length=30)
    datos = models.JSONField(default=dict)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class HistorialResponsablePrivacidad(models.Model):
    anterior = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                null=True, related_name="encargos_privacidad_anteriores")
    nuevo = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="asignaciones_privacidad")
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="cambios_responsable_privacidad")
    motivo = models.CharField(max_length=500)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-pk"]


class ConstanciaPrivacidad(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="constancias_privacidad")
    version = models.CharField(max_length=40)
    huella = models.CharField(max_length=64)
    texto = models.TextField()
    declaracion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Constancia de lectura de privacidad"
        verbose_name_plural = "Constancias de lectura de privacidad"
        ordering = ["-fecha"]
        constraints = [models.UniqueConstraint(fields=["usuario", "version", "huella"],
                                               name="constancia_privacidad_unica")]


class EventoAuditoria(models.Model):
    class Resultado(models.TextChoices):
        COMPLETADA = "COMPLETADA", "Cambio registrado"
        FINALIZADA = "FINALIZADA", "Solicitud finalizada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        FALLIDA = "FALLIDA", "Fallida"

    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="eventos_auditoria")
    origen = models.CharField(max_length=10, choices=[("WEB", "Web"), ("COMANDO", "Comando"), ("SISTEMA", "Sistema")], default="SISTEMA")
    solicitud_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    modulo = models.CharField(max_length=40, db_index=True)
    accion = models.CharField(max_length=40, db_index=True)
    resultado = models.CharField(max_length=15, choices=Resultado.choices, default=Resultado.COMPLETADA, db_index=True)
    modelo = models.CharField(max_length=100, blank=True)
    objeto_id = models.CharField(max_length=100, blank=True)
    campos = models.JSONField(default=list)
    antes = models.JSONField(default=dict)
    despues = models.JSONField(default=dict)
    ruta = models.CharField(max_length=240, blank=True)
    vista = models.CharField(max_length=150, blank=True)
    metodo = models.CharField(max_length=10, blank=True)
    estado_http = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-pk"]
        indexes = [models.Index(fields=["modelo", "objeto_id"], name="auditoria_objeto_idx"),
                   models.Index(fields=["fecha"], name="auditoria_fecha_idx")]
        verbose_name = "Evento de auditoría"
        verbose_name_plural = "Eventos de auditoría"

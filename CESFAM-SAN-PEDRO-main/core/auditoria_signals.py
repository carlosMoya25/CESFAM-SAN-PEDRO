"""Audita modelos concretos, con valores operativos permitidos; el resto solo nombra el campo."""
from django.apps import apps
from django.db import connections
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete, m2m_changed
from axes.signals import user_locked_out

from .auditoria import contexto_actual, intentar_registrar_evento, marcar_rechazo, registrar_evento


# shortcut: update/bulk_create no emiten señales; los saldos se auditan por sus movimientos. Ampliar al añadir nuevas escrituras masivas.
CAMPOS_SEGUROS = {
    "usuarios.Usuario": "is_active is_staff is_superuser debe_cambiar_clave revision_acceso anexo_id departamento_id",
    "auth.Group": "",
    "account.EmailAddress": "user_id verified primary",
    "socialaccount.SocialAccount": "user_id provider",
    "organizacion.Anexo": "tipo activo",
    "organizacion.Departamento": "activo",
    "inventario.CategoriaArticulo": "activo",
    "inventario.Articulo": "categoria_id stock_minimo activo",
    "inventario.TipoMovimiento": "activo",
    "inventario.MovimientoInventario": "tipo_movimiento_id anexo_origen_id anexo_destino_id usuario_id",
    "inventario.DetalleMovimiento": "movimiento_id articulo_id cantidad",
    "inventario.RecursoRequerimiento": "requerimiento_id articulo_id cantidad usuario_id movimiento_id",
    "requerimientos.TipoRequerimiento": "activo",
    "requerimientos.Prioridad": "nivel",
    "requerimientos.EstadoRequerimiento": "",
    "requerimientos.Requerimiento": "solicitante_id responsable_id anexo_id departamento_id tipo_requerimiento_id prioridad_id estado_id fecha_asignacion fecha_resolucion",
    "requerimientos.HistorialRequerimiento": "requerimiento_id usuario_id estado_anterior_id estado_nuevo_id",
    "usuarios.HistorialAdministracion": "administrador_id usuario_afectado_id accion",
    "usuarios.HistorialSeguridad": "usuario_afectado_id realizado_por_id tipo_accion",
    "farmacia.Medicamento": "articulo_id requiere_receta activo",
    "farmacia.LoteMedicamento": "medicamento_id fecha_vencimiento activo",
    "farmacia.MovimientoFarmacia": "tipo anexo_origen_id anexo_destino_id usuario_id fecha_recepcion importacion_id fila_importacion",
    "farmacia.DetalleMovimientoFarmacia": "movimiento_id lote_id cantidad vencimiento_registrado",
    "farmacia.ImportacionMedicamentos": "usuario_id estado modalidad cantidad_movimientos cantidad_lotes_creados cantidad_unidades cantidad_importada importada_at",
    "farmacia.ConfiguracionFarmacia": "bodega_central_id",
    "farmacia.StockPendienteFarmacia": "stock_original_id articulo_id anexo_id cantidad usuario_id movimiento_regularizacion_id",
    "core.ConstanciaPrivacidad": "usuario_id version",
    "core.ConfiguracionPrivacidad": "responsable_id revision validador_id contacto_validado_por_id contacto_validado_at canal_habilitado",
    "core.HistorialResponsablePrivacidad": "anterior_id nuevo_id administrador_id",
    "core.HistorialCanalPrivacidad": "realizado_por_id accion",
    "core.SolicitudDerecho": "solicitante_id tipo estado revision enviada_at fecha_limite respondida_por_id respondida_at",
    "core.EventoSolicitudDerecho": "solicitud_id accion realizado_por_id revision",
    "core.ReglaConservacion": "categoria dias revision",
    "core.CambioReglaConservacion": "regla_id realizado_por_id",
    "core.SimulacionConservacion": "realizado_por_id",
    "core.PoliticaRespaldos": "frecuencia hora dia_semana copias_diarias copias_semanales copias_mensuales prueba_cada_dias custodio_id suplente_id ubicacion revision",
    "core.CambioPoliticaRespaldos": "politica_id realizado_por_id",
    "core.ProgramacionRespaldos": "activa revision politica_revision activada_at",
    "core.CambioProgramacionRespaldos": "realizado_por_id activa politica_revision",
    "core.EjecucionProgramadaRespaldo": "politica_revision programada_para estado respaldo_id finalizada_at",
    "core.RespaldoBase": "motor tamano verificado_at",
    "core.PruebaRestauracion": "respaldo_id correcta",
    "core.DescargaRespaldo": "respaldo_id usuario_id",
}
IGNORADOS = {"last_login", "ultimo_latido", "listo", "diagnostico", "ejecutor", "verificacion"}
MODELOS = {}


def valores(instance):
    return {f.attname: getattr(instance, f.attname) for f in instance._meta.concrete_fields
            if not f.primary_key and not getattr(f, "auto_now", False) and not getattr(f, "auto_now_add", False)
            and f.name not in IGNORADOS}


def recordar(sender, instance, raw=False, using="default", **kwargs):
    if not raw:
        consulta = sender.objects.using(using)
        if connections[using].in_atomic_block:
            consulta = consulta.select_for_update()
        anterior = consulta.filter(pk=instance.pk).first() if instance.pk else None
        instance._auditoria_anterior = valores(anterior) if anterior else {}


def registrar_cambio(sender, instance, created=False, raw=False, eliminado=False, update_fields=None, **kwargs):
    if raw:
        return
    anterior = getattr(instance, "_auditoria_anterior", {})
    actual = valores(instance)
    if update_fields is not None:
        guardados = {sender._meta.get_field(c).attname for c in update_fields}
        actual = {c: v for c, v in actual.items() if c in guardados}
    campos = sorted(actual if created or eliminado else (c for c in actual if actual[c] != anterior.get(c)))
    if not campos:
        return
    seguros = MODELOS[sender]
    def resumen(datos):
        return {c: (str(datos[c]) if datos[c] is not None and not isinstance(datos[c], (int, bool, str)) else datos[c])
                for c in campos if c in seguros and c in datos}
    usuario_id = next((getattr(instance, campo + "_id") for campo in ("realizado_por", "administrador", "usuario", "user", "solicitante")
                       if getattr(instance, campo + "_id", None)), None)
    if usuario_id is None and getattr(instance, "movimiento_id", None):
        usuario_id = instance.movimiento.usuario_id
    modelo = instance._meta.label_lower
    modulo = instance._meta.app_label
    if modulo == "core":
        modulo = "respaldos" if "respaldo" in modelo or "restauracion" in modelo else "privacidad"
    persistidos = anterior | actual
    resultado = "FALLIDA" if persistidos.get("estado") in ("FALLIDA", "INTERRUMPIDA") or persistidos.get("correcta") is False else "COMPLETADA"
    registrar_evento(modulo=modulo, accion="ELIMINAR" if eliminado else "CREAR" if created else "MODIFICAR",
        modelo=modelo, objeto_id=str(instance.pk), usuario_id=usuario_id, resultado=resultado, campos=campos,
        antes=resumen(actual if eliminado else anterior), despues={} if eliminado else resumen(actual))


def eliminado(sender, instance, **kwargs):
    registrar_cambio(sender, instance, eliminado=True, **kwargs)


def recordar_grupo(sender, instance, using, **kwargs):
    # La eliminación del through por cascada no emite m2m_changed.
    usuarios = apps.get_model("usuarios.Usuario").objects.using(using).filter(groups=instance).prefetch_related("groups")
    instance._auditoria_miembros = {u.pk: sorted(grupo.pk for grupo in u.groups.all()) for u in usuarios}


def retirar_grupo(sender, instance, using, **kwargs):
    usuarios = apps.get_model("usuarios.Usuario").objects.using(using)
    for usuario_id, antes in getattr(instance, "_auditoria_miembros", {}).items():
        despues = list(usuarios.filter(pk=usuario_id, groups__isnull=False).order_by("groups__pk").values_list("groups__pk", flat=True))
        registrar_evento(modulo="usuarios", accion="CAMBIAR_ROLES", modelo="usuarios.usuario", objeto_id=str(usuario_id),
            campos=["groups"], antes={"groups": antes}, despues={"groups": despues})


def registrar_relacion(sender, instance, action, reverse, model, pk_set, using, **kwargs):
    relacion = RELACIONES[sender]
    if action.startswith("pre_"):
        if reverse:
            ids = list(model.objects.using(using).filter(**{relacion: instance}).values_list("pk", flat=True))
            ids = sorted(set(ids) | set(pk_set or ()))
            instance._auditoria_relacion = {pk: list(getattr(model.objects.using(using).get(pk=pk), relacion).values_list("pk", flat=True)) for pk in ids}
        else:
            instance._auditoria_relacion = {instance.pk: list(getattr(instance, relacion).values_list("pk", flat=True))}
    elif action.startswith("post_"):
        for pk, antes in getattr(instance, "_auditoria_relacion", {}).items():
            objeto = model.objects.using(using).get(pk=pk) if reverse else instance
            despues = list(getattr(objeto, relacion).order_by("pk").values_list("pk", flat=True))
            if sorted(antes) != despues:
                registrar_evento(modulo=objeto._meta.app_label, accion="CAMBIAR_ROLES" if relacion == "groups" else "CAMBIAR_PERMISOS" if relacion in ("permissions", "user_permissions") else "CAMBIAR_AUTORIZADOS",
                    modelo=objeto._meta.label_lower, objeto_id=str(pk), campos=[relacion], antes={relacion: sorted(antes)}, despues={relacion: despues})


def inicio(sender, request, user, **kwargs):
    contexto = contexto_actual.get()
    if contexto is not None:
        contexto["usuario"] = user
    intentar_registrar_evento(modulo="usuarios", accion="INICIO_SESION", usuario=user)


def salida(sender, request, user, **kwargs):
    intentar_registrar_evento(modulo="usuarios", accion="FIN_SESION", usuario=user)


def acceso_fallido(sender, **kwargs):
    marcar_rechazo()
    intentar_registrar_evento(modulo="usuarios", accion="ACCESO_FALLIDO", resultado="RECHAZADA")


def bloqueo(sender, **kwargs):
    marcar_rechazo()
    intentar_registrar_evento(modulo="usuarios", accion="BLOQUEO", resultado="RECHAZADA")


RELACIONES = {}


def conectar():
    for etiqueta, campos in CAMPOS_SEGUROS.items():
        modelo = apps.get_model(etiqueta)
        MODELOS[modelo] = set(campos.split())
        pre_save.connect(recordar, sender=modelo, dispatch_uid="auditoria.pre." + etiqueta)
        post_save.connect(registrar_cambio, sender=modelo, dispatch_uid="auditoria.post." + etiqueta)
        post_delete.connect(eliminado, sender=modelo, dispatch_uid="auditoria.delete." + etiqueta)
    pre_delete.connect(recordar_grupo, sender=apps.get_model("auth.Group"), dispatch_uid="auditoria.recordar_grupo")
    post_delete.connect(retirar_grupo, sender=apps.get_model("auth.Group"), dispatch_uid="auditoria.retirar_grupo")
    for etiqueta, campo in (("usuarios.Usuario", "groups"), ("usuarios.Usuario", "user_permissions"),
                            ("auth.Group", "permissions"), ("core.ConfiguracionPrivacidad", "autorizados")):
        sender = getattr(apps.get_model(etiqueta), campo).through
        RELACIONES[sender] = campo
        m2m_changed.connect(registrar_relacion, sender=sender, dispatch_uid="auditoria.m2m." + etiqueta + campo)
    for signal, receiver in ((user_logged_in, inicio), (user_logged_out, salida),
                             (user_login_failed, acceso_fallido), (user_locked_out, bloqueo)):
        signal.connect(receiver, dispatch_uid="auditoria.auth." + receiver.__name__)

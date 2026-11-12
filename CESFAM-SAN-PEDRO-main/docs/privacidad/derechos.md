# Mis datos y derechos y panel institucional

## Preparación personal

Ley 21.719 → Mis datos y derechos permite preparar borradores de acceso o rectificación, guardarlos con folio `PRIV-B-…`, consultarlos y editarlos. No se exige constancia de lectura. Las vistas personales siguen accesibles durante el cambio obligatorio de contraseña.

Un borrador no se envía automáticamente y no modifica el perfil del usuario. El panel institucional, el responsable de coordinación y las personas autorizadas no pueden consultar borradores ajenos.

## Configuración institucional y habilitación

En Ley 21.719 → Panel institucional:

1. Administración registra entidad responsable, correo institucional, cuenta activa que debe validar el contacto y cuentas activas autorizadas para responder. La coordinación sigue asignándose en «Asignar responsable».
2. La persona designada ingresa al panel y deja constancia de la verificación del contacto y su atención. Es una comprobación institucional manual; no se envía un correo automático ni se prueba técnicamente la propiedad del buzón.
3. Administración confirma que la institución aprobó el canal, el procedimiento de identidad y la atención y habilita expresamente la recepción.

No se asignan validadores, autorizaciones ni contactos automáticamente. La migración deja la recepción deshabilitada. Tener rol Administrador, Técnico TI o ser responsable de coordinación no autoriza por sí solo a consultar ni responder solicitudes.

Cambiar la configuración o a la persona coordinadora suspende nuevas recepciones y exige volver a validar y habilitar. El historial conserva autor, fecha, acción y datos de configuración. Los formularios usan revisión para rechazar cambios hechos desde pestañas desactualizadas.

Las cuentas del validador o de personas autorizadas deben reemplazarse o retirarse de la configuración antes de desactivarlas.

## Envío y recepción

Con el canal habilitado, el usuario revisa el borrador y confirma expresamente que lo envía y elige recibir el acuse y la respuesta en su cuenta del sistema. Se registra:

- Estado «Recibida», folio `PRIV-R-…`, fecha y hora de recepción.
- Entidad, contacto, revisión de configuración y medio de respuesta elegidos al recibir; los cambios posteriores del contacto no alteran este acuse.
- Fecha límite inicial de seguimiento: fecha local de recepción más 30 días corridos.
- Evento de envío y usuario que lo realizó.

El contenido recibido no se puede editar como borrador. Repetir el envío no genera una segunda recepción. Habilitar el canal nunca convierte automáticamente borradores en solicitudes presentadas.

La recepción es visible en el portal; no hay correos automáticos. Antes de activar, la institución debe validar que este medio de comunicación y el procedimiento de identificación sean adecuados para su operación y normativa aplicable. El contacto configurado no sustituye la política pública completa.

## Bandeja y respuestas

«Atender solicitudes» aparece únicamente a las cuentas activas incluidas en las autorizaciones. Estas personas pueden ver las solicitudes recibidas por la institución, excluidos sus propios trámites, y filtrar recibidas/respondidas. Los indicadores muestran la fecha límite inicial y señalan si vence hoy o está vencida.

Antes de responder deben confirmar la verificación de identidad, registrar una referencia del procedimiento y confirmar la publicación de la respuesta definitiva. La verificación se registra junto al actor y fecha de respuesta, sin solicitar copias de documentos ni credenciales. La referencia interna no se muestra al solicitante.

La respuesta queda disponible en la cuenta del solicitante y no se puede sobrescribir desde este formulario. No se puede responder la propia solicitud. Publicar una respuesta de rectificación no cambia automáticamente el perfil: los cambios efectivos requieren su procedimiento institucional.

Suspender nuevas recepciones no impide atender las solicitudes ya recibidas. Cambiar las autorizaciones retira acceso a las cuentas anteriores y permite a las nuevas continuar la bandeja existente; no altera autores ni respuestas previas. Los usuarios mantienen el seguimiento de sus solicitudes.

## Controles técnicos

- Propiedad vinculada a la sesión y filtro por autor en vistas personales; UUID en rutas, no folios como credencial.
- Autorización en servidor para configuración, validación y atención, independientemente de los enlaces visibles.
- CSRF y `no-store`; validación de tamaño, tipo y campos de rectificación.
- Clave de creación por usuario para evitar duplicados y control de revisión para ediciones/respuestas concurrentes.
- Transacciones y bloqueos de filas en configuración, recepción y respuesta.
- Historial de borradores, recepción, publicación y cambios institucionales.
- Sin adjuntos, descargas automáticas de todos los datos ni petición de RUT, contraseñas o información clínica.

## Límites y decisiones pendientes

Esto no acredita cumplimiento legal completo. La institución debe validar responsable legal y representación, política pública, bases legales, contacto, procedimiento de identidad y de comunicación, responsables efectivos, plazos de conservación y atención de derechos fuera del portal. Personas sin cuenta activa requieren los canales institucionales correspondientes.

Solo se implementan acceso y rectificación. No hay prórrogas de plazo, recordatorios por correo, rechazos estructurados, exportación automática ni otros derechos. Una denegación y sus fundamentos/vías de reclamación deben ajustarse al procedimiento institucional: el formulario no toma decisiones jurídicas automáticas. Los estados se limitan a Borrador, Recibida y Respondida.

Referencia: artículo 11 de la Ley 19.628 en su redacción modificada por la Ley 21.719, disponible en [BCN](https://www.bcn.cl/leychile/Navegar?idNorma=1209272&idVersion=2026-12-01).

## Despliegue y pruebas

Aplicar `core.0004_configuracionprivacidad_autorizados_and_more` antes de servir esta versión; ejecutar `collectstatic` si se actualizan estilos. Las pruebas automatizadas usan SQLite aislado. La concurrencia y el despliegue deben verificarse en MySQL/MariaDB de ensayo.

En esta entrega, la migración se aplicó correctamente a la base MySQL/MariaDB configurada y se actualizaron los estáticos. Pasaron 209 pruebas del proyecto con SQLite aislado y se verificaron nuevamente los 13 casos del canal tras los ajustes de formularios. No se configuraron contactos o autorizaciones ni se habilitó el canal en la base operativa. No se enviaron solicitudes o respuestas de prueba en esa base.

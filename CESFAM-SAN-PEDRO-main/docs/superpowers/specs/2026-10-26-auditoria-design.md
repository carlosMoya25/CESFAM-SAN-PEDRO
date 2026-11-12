# Auditoría central y diagnóstico del CESFAM

## Acuerdos

El usuario solicitó registros de actividad de todos los módulos y confirmó que Administración y Técnico TI pueden consultar toda la auditoría. Se conserva el diseño conversado: auditoría persistente y diagnóstico técnico correlacionados, sin contraseñas, tokens, cookies, formularios, consultas de búsqueda ni contenidos sensibles.

## Enfoque y alcance

Se conserva la aplicación Django y sus historiales. Una tabla EventoAuditoria en core registra metadatos futuros, sin reconstruir actividad anterior. No se agregan dependencias. Frente a duplicar llamadas en cada vista, se observan modelos explícitamente autorizados: catálogos, cuentas, relaciones de roles, requerimientos y los registros de movimientos e historiales existentes. Solo se copian campos operativos de una lista permitida; para campos personales/libres se registra que cambiaron, sin sus valores. Los saldos actualizados mediante QuerySet.update se representan por sus movimientos existentes; esto no es un auditor SQL universal ni observa escrituras hechas directamente a la base.

Un middleware registra consultas y solicitudes dinámicas con ruta normalizada, método, estado HTTP, duración e identificador generado en el servidor. No guarda URL con parámetros, cuerpo, cabeceras de autenticación ni IP. Una respuesta HTTP exitosa significa solicitud finalizada, no cambio de negocio confirmado. Los guardados del negocio tienen sus propios eventos. Se conserva el actor del cierre de sesión y se restablece el contexto al terminar cada solicitud.

La observación de cambios crea el evento en la misma transacción de los servicios existentes. ATOMIC_REQUESTS cubre las vistas propias, allauth y el admin; el middleware de navegación queda fuera de la transacción de la vista. Se conservan las transacciones de servicios y se añaden transacciones cortas a la persistencia de los comandos. Esto añade una transacción por vista, un coste a medir con la carga real. Un fallo del registro obligatorio revierte el cambio; los fallos del registro de navegación solo producen diagnóstico seguro y no impiden servir una respuesta. Los comandos de mantenimiento y respaldos tienen origen e identificador propios; no se guardan sus argumentos ni excepciones completas.

## Datos y protección

EventoAuditoria: fecha UTC, usuario opcional, origen WEB/COMANDO/SISTEMA, UUID de correlación, módulo, acción, resultado, modelo e identificador del objeto, referencia a historial, cambios permitidos, ruta normalizada, método, estado HTTP y duración. El panel presenta fechas en America/Santiago.

El diagnóstico JSON usa logging estándar y stdout/stderr. Solo emite campos permitidos; en errores incluye clase de excepción y posiciones de pila, sin mensajes arbitrarios, variables locales ni líneas de código. Django conserva el manejo de respuestas de error. No se escribe un archivo compartido desde los tres procesos Gunicorn. Docker limita la rotación del diagnóstico por tamaño; no se borran eventos de auditoría automáticamente.

## Consulta

Panel y detalle solo GET, protegidos por sesión activa y rol Administrador, Técnico TI o superusuario. Paginación de 25 eventos, filtros por fecha, actor, módulo, resultado, tipo/modelo, acción y UUID. Los filtros inválidos muestran errores y ningún resultado. El acceso al propio panel también queda registrado. El admin de Django ofrece los eventos solo a esos roles con staff y solo para consulta; no permite altas, cambios ni borrado individual/masivo. No hay exportaciones en esta etapa.

## Comprobación y despliegue

Pruebas de ambos roles y denegación de otros usuarios, protección de datos sensibles, aislamiento de contexto, filtros, login/logout/fallos, errores HTTP, transacciones/reversión y cobertura de cada dominio. Ejecutar la suite completa en SQLite aislado, migraciones y comprobaciones de plantillas. Preparar migración core; no aplicarla a la base compartida sin comprobar su destino. No se inicia un ejecutor ni se envían logs a servicios externos.

## Límites operativos

No se graban teclas, clics, estáticos ni cada consulta SQL. Las modificaciones de QuerySet.update/bulk_create nuevas deberán pasar por un servicio auditado o crear un evento explícito. La tabla crece: conservación y archivo externo requieren política institucional posterior. El usuario de base de datos con privilegios suficientes aún puede alterar registros: la aplicación por sí sola no acredita inmutabilidad frente a un administrador SQL.

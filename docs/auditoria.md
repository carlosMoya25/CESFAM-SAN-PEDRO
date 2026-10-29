# Auditoría y diagnóstico

## Consulta y permisos

El menú **Auditoría**, en `/auditoria/`, está disponible para cuentas activas con rol **Administrador**, **Técnico TI** o superusuario. Ambos roles consultan toda la auditoría. No concede acceso adicional a los módulos de negocio ni al admin técnico: este último sigue exigiendo staff. Los eventos en el admin son de solo lectura y mantienen la misma restricción de rol.

El panel tiene 25 filas por página y filtros por fechas de Chile, usuario, módulo, acción, resultado, modelo/ID y UUID de seguimiento. Los errores de filtro dejan la consulta sin resultados. El detalle muestra metadatos y cambios de campos permitidos; su enlace de seguimiento reúne los eventos de la misma solicitud o comando. Cada consulta al panel también se registra. No hay exportación, edición ni borrado de eventos en esta etapa.

## Lectura de resultados

- **Cambio registrado (COMPLETADA):** se creó, modificó o eliminó un registro observado. Puede referenciar un movimiento o historial del negocio.
- **Solicitud finalizada (FINALIZADA):** se sirvió una consulta o petición. Un 200/302 no acredita que se guardó un cambio de negocio.
- **Rechazada:** acceso denegado, error de validación detectado o conflicto de negocio.
- **Fallida:** respuesta 500, comando fallido, comprobación de recuperación fallida o ejecución de respaldo interrumpida.

La columna Responsable muestra el correo de la cuenta asociada al evento, también cuando se inicia sesión con Google. Antes de completar el acceso, las consultas al login y las redirecciones pueden no tener usuario y se muestran como «Sesión no iniciada». Los eventos sin actor de comandos y del sistema tienen etiquetas propias. Un intento fallido no acredita que el visitante sea dueño del correo introducido; no se atribuye ese intento a una cuenta por ese dato. No se reasignan eventos anónimos antiguos por inferencia.

Las fechas se almacenan en UTC y se muestran en America/Santiago. `X-Request-ID` permite relacionar la respuesta con los eventos y el diagnóstico del servidor; es un identificador generado por el servidor, no una credencial ni un identificador de sesión.

## Cobertura

| Área | Eventos observados |
| --- | --- |
| HTTP | Consultas de pantallas, fichas, formularios, admin y auditoría; solicitudes de modificación, rechazos y errores. Se excluyen estáticos. |
| Identidad | Login local/Google, logout, fallos y bloqueos; cambios de cuentas, roles, permisos y retirada de roles por eliminación de grupos. |
| Organización y catálogos | Altas, cambios y eliminaciones de ubicaciones, departamentos, artículos, categorías, medicamentos, lotes y catálogos TI. |
| Operaciones | Requerimientos y su historial; movimientos generales, detalles y recursos; movimientos/lotes de farmacia, importaciones y conciliaciones. |
| Privacidad | Constancias, responsable, configuración/autorizaciones del canal, derechos y sus eventos, propuestas e informes de conservación. |
| Respaldos | Política, programación, ejecuciones e interrupciones, copias, pruebas y descargas. Los comandos tienen contexto COMANDO y UUID propio. |

`core/auditoria_signals.py` enumera los modelos y los campos cuyos valores pueden copiarse. Los demás campos concretos solo se nombran cuando cambian. Los guardados parciales `save(update_fields=...)` solo registran los campos persistidos. Las actualizaciones de latido/diagnóstico del ejecutor y de último login no generan cambios de negocio adicionales.

Los movimientos existentes explican las cantidades; la auditoría no reemplaza los historiales ni reconstruye actividad anterior a su instalación. Para operaciones directas con servicios, el usuario se deriva del registro cuando está disponible. Una tarea sin usuario/contexto identificable queda como sistema, sin inventar un responsable humano.

## Datos excluidos

No se guardan cuerpos de petición/respuesta, contraseñas ni sus hashes, cookies, tokens, claves, cabeceras, IP ni parámetros de URL. Los campos personales y textos libres —descripciones, observaciones, respuestas de derechos, contenido CSV, correos y teléfonos— no se copian. Se conservan únicamente sus nombres de campo modificados. El panel resuelve la identidad actual del actor mediante su ID de usuario, sin duplicar su ficha en cada evento.

Las rutas HTTP son patrones del servidor y nombres de vistas. De los parámetros de ruta solo se conserva el ID numérico/UUID del objeto; rutas inexistentes no copian la cadena enviada por el visitante.

## Integridad y fallos

`ATOMIC_REQUESTS` incluye las vistas propias, allauth y admin en la misma transacción de sus eventos. Los servicios ya transaccionales conservan sus límites; los puntos de registro de respaldos y los comandos añaden transacciones cortas, sin mantener una transacción SQL abierta durante el volcado completo. Los callbacks de diagnóstico de cambios se emiten al confirmar la transacción. Si la auditoría obligatoria falla, el cambio se revierte. Si falla la auditoría auxiliar de navegación/autenticación, se conserva la respuesta y se informa mediante diagnóstico seguro.

La copia y el manifiesto parciales se retiran si falla el registro final de respaldo. Los errores de comandos se muestran con una referencia de seguimiento; el diagnóstico conserva clase y posiciones de pila sin el mensaje arbitrario de la excepción.

Django/Python emiten JSON por consola mediante `core.logging.FormatoSeguroJSON`. No se usa un archivo compartido entre procesos Gunicorn. El Compose limita el diagnóstico de cada servicio a cinco archivos de 10 MB mediante el driver `json-file`; esos límites no eliminan auditoría en MySQL. La configuración del proxy y otros servicios externos debe revisarse por separado.

## Instalación

1. Respaldar y revisar el entorno de destino antes de aplicar migraciones.
2. Aplicar migraciones antes de servir esta versión: `venv/bin/python manage.py migrate`. La nueva es `core.0010_eventoauditoria`.
3. Ejecutar `collectstatic --noinput` para el despliegue, si corresponde, y reiniciar web/ejecutor con la versión actualizada. La auditoría no activa el ejecutor de respaldos.
4. Comprobar el menú y el acceso con Administrador, Técnico TI y una cuenta sin esos roles; revisar que ambas cuentas autorizadas ven eventos.
5. Definir conservación/archivo de auditoría y supervisar crecimiento y espacio. La aplicación no borra automáticamente estos eventos.

## Límites

- Se registra actividad futura; no se inventan registros anteriores ni se graban teclas, clics o cada consulta SQL.
- QuerySet.update/bulk_create no emiten señales de modelo. Los saldos masivos actuales tienen movimientos; las interrupciones de respaldo pasan por save. Toda nueva escritura masiva debe crear un evento o conservar un movimiento auditado en la misma transacción.
- Las escrituras directas desde SQL quedan fuera. El bloqueo de edición en la aplicación no protege frente a un administrador de base de datos con privilegios suficientes; requiere controles y copias externas.
- Código nuevo que guarde modelos fuera de HTTP debe conservar una transacción y contexto de auditoría cuando corresponda. Los receptores no pueden convertir retroactivamente un guardado autocommit en transacción.
- Se añade una transacción por vista y escritura de metadatos. La carga y los bloqueos concurrentes se deben comprobar en MySQL antes de producción.


## Activación comprobada — 26/10/2026

Tras un fallo de acceso Google se confirmó en la base MySQL/MariaDB configurada que faltaban la tabla `core_eventoauditoria` y la migración `core.0010_eventoauditoria`. El único paso pendiente del plan era esa migración; se aplicó correctamente. Se comprobó una inserción de auditoría dentro de una transacción y se revirtió el registro de prueba. No se cambiaron cuentas, contraseñas ni vinculaciones Google durante la corrección.

Las 34 pruebas aisladas de registro/autenticación y auditoría pasaron. El intercambio real con Google requiere iniciar un nuevo intento desde la pantalla de acceso; no reutilizar la URL del callback fallido.

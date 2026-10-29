# Inventario inicial de datos y controles

Estado: documento técnico de trabajo, pendiente de validación institucional. No acredita cumplimiento legal completo.

## Tratamientos identificados

| Área | Datos personales | Finalidad operativa | Acceso propuesto / actual | Conservación |
| --- | --- | --- | --- | --- |
| Cuentas | Nombres, apellidos, correo, teléfono, anexo, departamento, roles, hash de contraseña, fechas de acceso | Identificación y administración de acceso | Administración; datos propios en sesión | Pendiente de definir por la institución |
| Autenticación | Sesiones, identificadores OAuth, datos de perfil recibidos de Google, registros de intentos de Axes | Autenticación y prevención de accesos indebidos | Sistema y administración autorizada | Sesión de 15 minutos de inactividad; otros registros pendientes de definir |
| Requerimientos TI | Solicitante, responsable, título, descripción, solución, observaciones, fechas e historial | Atención y continuidad del soporte | Solicitante en sus solicitudes; técnico responsable; administrador. Pendientes compartidos muestran categoría, ubicación, prioridad y fecha antes de asignarse | Pendiente de definir |
| Inventario | Autor de movimientos, motivos, recursos utilizados | Control y trazabilidad de existencias | Roles de inventario y administración; referencias en requerimientos según su acceso | Pendiente de definir |
| Farmacia | Autor, movimientos, proveedor, documentos, observaciones, nombre y contenido de importaciones | Control de existencias, recepción y trazabilidad | Farmacia y administración | Pendiente de definir; la caducidad de vista previa no elimina filas |
| Historiales | Usuarios afectados, administrador, acción, descripción y fecha | Trazabilidad de administración y seguridad | Administración; historiales operativos según módulo | Pendiente de definir |
| Constancias | Usuario, fecha, versión, copia del aviso y declaración, huella | Evidencia de declaración de lectura | Usuario: constancia propia actual. Administrador y Técnico TI: listado. Admin Django autorizado: detalle | Pendiente de definir |
| Responsable de atención de privacidad | Persona asignada, asignaciones anteriores, administrador, motivo y fecha del cambio | Continuidad de atención de privacidad | Usuarios autenticados: asignación actual. Administradores: cambio e historial | Pendiente de definir |
| Borradores de derechos | Usuario, tipo de petición (acceso/rectificación), descripción, dato a corregir, valor propuesto, folio, revisión y fechas | Preparación personal de una futura solicitud | Solo su autor desde las vistas de usuario, incluidos administradores que únicamente ven los propios. Sin panel institucional habilitado | Pendiente de definir |
| Canal y solicitudes recibidas | Entidad, contacto, validador, autorizaciones, acuse, fechas de recepción y respuesta, respuesta y referencia interna de verificación | Atención institucional de acceso y rectificación, previa habilitación explícita | Administración configura sin acceso automático al contenido; validador verifica contacto; personas expresamente autorizadas atienden solo solicitudes enviadas, excluidas las propias. Solicitante ve su acuse y respuesta | Pendiente de definir |
| Propuestas de conservación y simulaciones | Administrador, fechas de cambios, plazos y fundamentos propuestos, cantidades agregadas y criterios de cada informe | Planificación y revisión institucional de conservación | Solo administración; los resultados no contienen identidades ni contenidos de los registros evaluados | Pendiente de definir; las propuestas no autorizan una depuración |
| Respaldos y registros técnicos | Pueden contener las categorías anteriores | Recuperación y diagnóstico | Responsables de infraestructura; verificar acceso real | Pendiente de definir y comprobar en despliegue |
| Registro de respaldos y pruebas | Identificador de copia, motor, versión, tamaño, huella, fechas y resultados técnicos | Seguimiento de creación y comprobación de recuperación | Panel solo para administración; archivos y claves sin descarga web | Pendiente de definir |

No ingresar pacientes, diagnósticos, contraseñas ni tokens en texto libre. La advertencia no sustituye controles ni revisión de datos ya existentes. Los campos de proveedor/documentos también pueden identificar personas naturales.

## Matriz de permisos aplicada en esta etapa

- Funcionario: crea y consulta sus solicitudes; no administra cuentas ni opera solicitudes ajenas.
- Técnico TI: ve una cola mínima de pendientes, puede tomar uno y consultar/gestionar los asignados a sí mismo. No puede consultar el detalle de los asignados a otro técnico.
- Administrador: consulta y gestiona solicitudes; administra cuentas y ejecuta la desactivación con continuidad.
- Constancias: se conserva el acceso solicitado para administradores y técnicos TI. La institución debe validar la necesidad de acceso de todos los técnicos.
- Inventario y farmacia mantienen sus roles independientes. Esta etapa no certifica una auditoría exhaustiva de esos módulos ni de la infraestructura.

## Desactivación y continuidad

1. Administración abre «Revisar desactivación» en el detalle del usuario.
2. Revisa solicitudes no cerradas ni canceladas (incluidas las resueltas pendientes de cierre).
3. Selecciona un técnico TI activo si existen pendientes e indica un motivo sin antecedentes sensibles.
4. Confirma. Una transacción cambia los responsables, añade eventos de historial, desactiva la cuenta e incrementa su revisión de acceso.
5. Las sesiones previas dejan de autenticarse en su siguiente solicitud, incluso si se reactiva la cuenta antes. No se interrumpen operaciones que ya estaban en ejecución.
6. La reactivación requiere un nuevo inicio de sesión y no restaura asignaciones antiguas. La edición normal de usuarios no permite saltarse este flujo cambiando su estado.

Las solicitudes cerradas/canceladas y las autorías de historiales no se modifican. No se eliminan datos personales durante este flujo.

## Decisiones institucionales pendientes

En «Ley 21.719 → Asignar responsable», administración puede designar una cuenta activa como encargada de coordinar la atención. Se conserva historial, se rechazan formularios desactualizados y se exige reemplazar a esa persona antes de desactivar su cuenta. La asignación no concede permisos administrativos ni cambia la entidad responsable legal. No se ha seleccionado ninguna persona automáticamente.

- Entidad responsable, representante y contacto para derechos e incidentes.
- Base legal y finalidad validada de cada tratamiento; no se presume consentimiento por usar la plataforma o leer el aviso.
- Plazos por categoría, excepciones de conservación y ciclo de respaldos.
- Proveedores, ubicación de datos, contratos y transferencias internacionales que correspondan.
- Encargados de atender derechos y gestionar incidentes; capacitación y evaluación de riesgos/impacto aplicable.

## Despliegue y validación

La migración `usuarios.0007_usuario_revision_acceso` fue aplicada correctamente a la base MySQL/MariaDB configurada en esta tarea, tras consultar el plan. Añade la columna de revisión de acceso; no desactiva usuarios ni reasigna solicitudes existentes. En otros entornos ejecutar `venv/bin/python manage.py migrate` antes de servir esta versión.

Verificar con cuentas de prueba los permisos, desactivación, reasignación y reactivación. Probar las migraciones y concurrencia en un entorno MySQL de ensayo antes del despliegue. Las pruebas automatizadas locales usan SQLite aislado; no verifican los bloqueos de fila de MySQL ni la infraestructura real.

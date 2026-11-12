# Conservación: propuestas y simulación

## Acceso y alcance

Ley 21.719 → Conservación de datos está disponible solo para administradores activos. El rol Técnico TI, la validación del contacto y la autorización para responder derechos no conceden acceso a esta pantalla.

Esta etapa permite proponer plazos, documentar su fundamento y obtener informes de recuentos. No existe una acción de eliminación o anonimización, ni comandos de limpieza ni trabajos programados. Guardar o simular no aprueba una política institucional y no modifica registros de las fuentes evaluadas.

## Propuestas

Las siete categorías empiezan sin plazo. Se registran días propuestos, fundamento o referencia institucional y revisión. Un valor vacío significa «Sin definir»; para un plazo numérico se exige fundamento. Los límites de entrada son 1 a 36.500 días por validación técnica, sin constituir recomendación legal.

Cada cambio guarda administrador, fecha, valores anteriores y nuevos. Un control de revisión rechaza formularios desactualizados; guardar lo mismo no duplica el historial. No se altera la configuración del canal de derechos al modificar una propuesta.

## Criterios de simulación

| Categoría | Alcance por estado | Fecha utilizada |
| --- | --- | --- |
| Borradores de derechos | Solo BORRADOR | Última actualización |
| Solicitudes de derechos | Solo RESPONDIDA | Publicación de respuesta |
| Importaciones de farmacia | Solo PENDIENTE sin movimientos vinculados | Creación |
| Sesiones | Solo vencidas, almacenadas en la tabla de sesiones de Django | Vencimiento; los días se cuentan después de esa fecha |
| Requerimientos TI | Solo Cerrado o Cancelado | Última actualización o último evento del historial, la más reciente |
| Constancias | Solo versiones distintas del aviso actual por versión/huella | Fecha de lectura |
| Cuentas | Solo inactivas | Última desactivación en el historial administrativo |

Cuentas sin un evento de desactivación no se clasifican por antigüedad; no se infiere esa fecha de la creación ni del último inicio de sesión. Las importadas, sesiones activas, solicitudes abiertas y constancias actuales quedan fuera del criterio temporal de su categoría.

Una categoría sin plazo no se evalúa. Para generar el informe debe existir al menos una propuesta con días definidos.

## Informes

Se guardan cantidades agregadas por categoría: total de la fuente, alcance por estado, registros sin fecha suficiente y registros anteriores al corte. El informe conserva la revisión de cada propuesta, sus días, el corte usado en hora de Chile continental y la versión/huella del aviso vigente.

No se guardan nombres, correos, contenidos ni identificadores de los registros evaluados en el resultado JSON. La autoría del informe corresponde al administrador que lo generó. Una propuesta posterior no cambia un informe existente.

Los totales no deben sumarse como si fueran fuentes independientes: borradores y derechos respondidos comparten tabla. Los conteos son orientativos y las operaciones concurrentes pueden cambiar el estado real después de consultar.

## Antes de cualquier depuración futura

La institución debe definir y validar sus plazos, obligaciones y excepciones de conservación por finalidad, además de medidas de preservación, litigios, vínculos entre datos y reglas de respaldos. Un registro antiguo no equivale a un registro eliminable.

Queda pendiente implementar un procedimiento de aprobación y ejecución de una eventual depuración, con alcance exacto, controles de dependencias y auditoría. No se ha habilitado una eliminación futura automática al guardar propuestas.

Esta simulación no analiza ficheros de respaldo, registros del servidor ni archivos externos. El siguiente trabajo operativo debe cubrir protección de respaldos, restauración y retención de esas copias, además de incidentes.

Referencia: principio de conservación y excepciones en [Ley 21.719, BCN](https://www.bcn.cl/leychile/Navegar?idNorma=1209272&idVersion=2026-12-01). El documento no fija plazos legales para las categorías del proyecto.

## Despliegue y pruebas

Aplicar `core.0005_reglaconservacion_cambioreglaconservacion_and_more` antes de usar la pantalla. La migración crea únicamente tablas de propuestas, cambios e informes; no carga plazos ni ejecuta simulaciones sobre la base operativa.

Las pruebas automatizadas usan SQLite aislado. Verificar las consultas y concurrencia en MySQL/MariaDB de ensayo antes de depender operativamente de los informes.

En esta entrega se aplicó correctamente la migración en la base MySQL/MariaDB configurada. Pasaron 222 pruebas del proyecto con SQLite aislado. No se cargaron plazos, no se generaron informes de prueba en la base operativa y no se eliminó ningún registro.

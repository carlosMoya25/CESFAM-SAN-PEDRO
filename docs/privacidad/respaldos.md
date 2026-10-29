# Copia SQL cifrada y prueba de recuperación

## Qué incorpora

- Copia lógica SQL de la base MySQL/MariaDB completa: estructura, datos, disparadores, rutinas y eventos que el usuario de respaldo pueda leer. Requiere tablas InnoDB y no realizar cambios de esquema durante la copia.
- Cifrado AES-256-GCM en flujo: el volcado no se guarda como SQL legible al generar la copia. Usa nonce aleatorio y autentica el formato.
- Manifiesto privado firmado con una clave derivada distinta, con huella SHA-256 de la copia y recuentos extraídos del propio volcado (una inserción por fila).
- Clave local de 32 bytes con permisos 0600; directorios privados 0700. La clave no se reemplaza automáticamente ni se imprime.
- Prueba mediante contenedor de la misma familia y versión mayor/menor, sin red, sin puertos publicados y con base temporal en tmpfs. No recibe credenciales de producción ni tiene montado su almacenamiento.
- Historial de pruebas con resultado separado de la creación. Una importación o recuento fallidos no marcan una copia como verificada.
- Panel restringido a administradores y Técnico TI: Ley 21.719 → Respaldos y recuperación. Permite descargar una copia cifrada existente junto con su manifiesto y consultar el historial de descargas. No hay restauración sobre producción ni ejecución de comandos desde el navegador.

Los contenedores usan imágenes oficiales locales `mariadb:X.Y` o `mysql:X.Y`. La herramienta no descarga imágenes automáticamente ni acepta destinos de restauración arbitrarios.

## Traslado manual al servidor Windows

1. Administración o Técnico TI abre Ley 21.719 → Respaldos y recuperación y revisa la fecha y el resultado de la prueba de la copia.
2. Pulsa **Descargar copia cifrada (ZIP)**. El servidor verifica el manifiesto firmado, el tamaño y la huella del contenido antes de ofrecerlo. Una copia pendiente de restauración puede descargarse; eso no la convierte en una copia comprobada.
3. Traslada el ZIP a la carpeta privada del servidor Windows del CESFAM. Mantiene juntos el archivo `.cesfam` y su manifiesto `.json` y custodia la clave por separado. No debe extraer el SQL en una carpeta compartida.
4. En **Historial de descargas** puede revisar usuario, fecha y copia entregada. Se registra la preparación de la descarga, no la recepción completa del navegador ni el almacenamiento en Windows. No existe todavía confirmación de recepción en destino.

La descarga requiere sesión activa con rol autorizado y POST con CSRF; no hay enlace público ni descarga de la clave. Las respuestas no se almacenan en caché. El historial conserva la huella de la copia y no puede editarse desde el panel. La descarga no genera un respaldo nuevo ni incorpora archivos media o configuración. Usar HTTPS al desplegar el servicio.

## Crear una copia

Primera ejecución, desde el entorno de mantenimiento:

```sh
venv/bin/python manage.py crear_respaldo --crear-clave
```

Las siguientes ejecuciones omiten `--crear-clave`. Esa opción crea la clave únicamente si no existe; no cambia una existente.

Si el cliente local no admite la autenticación del servidor, se puede usar su imagen oficial local:

```sh
docker pull mariadb:11.4
venv/bin/python manage.py crear_respaldo --cliente-docker
```

Si esa es la primera ejecución de la instalación, añade también `--crear-clave`.

El comando determina la imagen compatible a partir de la versión de origen. En este modo, solo el contenedor del cliente tiene conectividad para leer la base por TLS. Se monta temporalmente un directorio privado de credenciales en modo de solo lectura; no se monta la clave de cifrado ni la carpeta de copias. El cliente se retira al finalizar.

El cliente MySQL requiere TLS; el cliente MariaDB requiere TLS y validación del servidor. Las opciones `ssl` (ca/cert/key) de la conexión Django se pasan al cliente si están configuradas. MariaDB 11.4 admite su procedimiento de TLS sin configuración con autenticación compatible. No se desactivan las comprobaciones para resolver errores de conexión.

Para que la copia se registre deben existir las tablas de `core.0006_respaldobase_pruebarestauracion`. Fallos del volcado retiran la copia parcial y no generan un registro de éxito. El manifiesto acompaña a cada copia: debe conservarse junto al archivo cifrado.

## Probar una recuperación

Con Docker Desktop/Engine disponible y la imagen oficial correspondiente ya descargada:

```sh
venv/bin/python manage.py verificar_respaldo UUID_DE_LA_COPIA
```

Se comprueba el manifiesto y la huella, se descifra en un directorio temporal privado y se autentica antes de importar. El contenedor de prueba tiene `--network=none`, no publica puertos y no recibe rutas de la base operativa. Se crea la base dentro de ese contenedor y se importa el SQL. Se comparan los recuentos de todas las tablas base contra los extraídos del volcado. Después se retira el contenedor y el directorio temporal.

Se limita la prueba a 2 GB de RAM, 2 CPU y 1 GB de tmpfs para datos. Si no alcanza o falla el arranque/importación, se registra fallo. El plan no amplía automáticamente recursos ni cambia la base de origen. Si no se puede retirar un contenedor, el panel informa su nombre para mantenimiento y no marca la prueba como correcta.

La prueba demuestra autenticación del archivo, importación SQL y coincidencia de recuentos. No verifica flujos de la aplicación, credenciales externas, contenido semántico de cada campo ni equivalencia funcional de rutinas/eventos. Los eventos permanecen desactivados durante la prueba.

## Custodia y despliegue

### Definición institucional recibida el 25 de octubre de 2026

- Destino previsto: servidor Windows local (on-premise) del CESFAM, en un equipo distinto del que ejecuta la aplicación.
- Responsable operativo de respaldos: Técnico TI del CESFAM. Esta responsabilidad no equivale a designar al responsable institucional de protección de datos ni concede permisos adicionales en la aplicación.
- Pendiente: identificar nombre o dirección del equipo, ruta privada y método de conexión desde el servidor de la aplicación; definir frecuencia, conservación, custodio de la clave y suplencia.
- Esta definición documenta el destino previsto; no configura una transferencia ni acredita que existan copias en ese servidor. No se registran direcciones, credenciales ni claves en esta guía.
- Si el destino comparte host o ubicación con la aplicación, debe preverse una copia adicional protegida frente a la pérdida de ese host o lugar. La clave debe conservarse por un procedimiento separado del almacenamiento de copias.

Valores predeterminados:

- Copias y manifiestos: `respaldos_locales/base_de_datos/`.
- Clave: `.secrets/backup.key`, fuera de la carpeta de copias.

Se pueden configurar `BACKUP_ROOT` y `BACKUP_KEY_FILE`. Se rechazan rutas públicas de estáticos/media, enlaces simbólicos directos y una clave dentro de la carpeta de copias.

`.gitignore` y `.dockerignore` excluyen copias, claves y `.env`; no deben añadirse a Git ni a la imagen. Docker Compose incorpora volúmenes privados separados para copias y claves. Un cambio del Compose local no implica que el servidor desplegado ya lo tenga aplicado.

La institución debe guardar una copia de la clave por un procedimiento seguro y separado, y trasladar copias/manifiestos a almacenamiento protegido fuera del servidor. Los dos volúmenes en el mismo host no constituyen por sí solos recuperación ante pérdida del host. Perder la clave impide descifrar las copias. No debe rotarse ni reemplazarse sin un plan de conservación de claves anteriores.

Este respaldo no incluye archivos media, código, `.env`, claves, usuarios/permisos globales del servidor SQL ni configuración del sistema operativo. Su protección y recuperación necesitan un procedimiento adicional. No se ha configurado una frecuencia automática, conservación o limpieza de copias.

Las copias se generan en el equipo donde se ejecuta el comando. El panel solo detecta archivos en el almacenamiento privado de ese despliegue: compartir la base de registros entre desarrollo y servidor no traslada los archivos ni las claves entre equipos.

Si se pierde el registro en Django, el archivo y su manifiesto firmado identifican la copia. El módulo criptográfico permite verificar y descifrar sin consultar la base. El comando de prueba registra su resultado en la base configurada y por ello presupone que esa conexión está disponible; no es un restaurador automático de producción ni sustituye el procedimiento de recuperación total.

## Antes de una depuración

Conservar una copia externa recuperable y su clave, comprobar la restauración y realizar pruebas funcionales en un entorno separado. Las propuestas de conservación siguen sin ejecutar eliminaciones. Una copia no autoriza borrar registros ni fija sus plazos de conservación.

## Validación de esta entrega

Se aplicó `core.0006_respaldobase_pruebarestauracion` a la base configurada. El cliente MySQL local no admite el complemento de autenticación del servidor MariaDB; la copia real se creó con el cliente oficial MariaDB 11.4 mediante Docker y TLS con comprobación del servidor.

Copia local: `8ceb75f7-2847-4ba2-9b7e-148cdf3d183b`, 386.373 bytes cifrados. La importación en MariaDB temporal aislado verificó 58 tablas y 1.104 filas; se retiraron los contenedores del cliente y de restauración. En la base configurada solo se añadieron los registros de control del respaldo y de la prueba; no se restauró sobre ella.

La clave local se conserva en `.secrets/backup.key` con permisos privados. No se ha trasladado a custodia externa, no se ha enviado una copia a otros servicios ni se ha activado una frecuencia automática. Los volúmenes del Compose se prepararon en el código; no se desplegó una nueva imagen del servicio web.

## Política configurable en el panel

Administración y Técnico TI pueden registrar en **Respaldos y recuperación → Política de respaldos**:

- Frecuencia prevista (manual, diaria, cada 12 horas o semanal), hora de Chile continental y día para la frecuencia semanal.
- Cantidades de copias diarias, semanales y mensuales que se prevé conservar. Vacío significa pendiente; 0 indica que no se conservará esa categoría. No hay plazos legales ni cantidades preseleccionados.
- Intervalo previsto entre pruebas de recuperación.
- Custodio principal y suplente de la clave: personas distintas con cuenta activa. La designación no concede acceso al panel ni a archivos. Las cuentas desactivadas se señalan como pendientes de reemplazo.
- Procedimiento de custodia, confirmación de ubicación física y plan frente a la pérdida de ese lugar. Si ambos servidores están en la misma ubicación, debe describirse el plan adicional. Registrar un plan no verifica su ejecución.

Se permite guardar una definición parcial, con lista explícita de pendientes. No se ingresan claves, contraseñas ni credenciales: solo referencias del procedimiento. Cada guardado exige un motivo y registra usuario, fecha, revisión y valores anteriores/nuevos; el panel muestra los últimos 10 cambios. Una pestaña desactualizada no puede sobrescribir una revisión posterior.

Esta configuración **documenta la política**: no instala un programador, no crea nuevas copias, no transfiere archivos al servidor Windows, no prueba restauraciones automáticamente y no elimina respaldos. La activación y verificación de esos procedimientos de mantenimiento sigue pendiente. Su conservación es independiente de la política de conservación de solicitudes y otros datos del sistema.

## Generación automática de copias SQL

El panel incorpora **Respaldos automáticos** con activación/suspensión por Administración o Técnico TI, motivo obligatorio, confirmación, revisión vigente e historial. Está desactivado inicialmente. Guardar una política la suspende para exigir una nueva confirmación; no cancela una copia que ya esté iniciada.

La solicitud de activación requiere política completa y frecuencia diaria/cada 12 horas/semanal. Puede guardarse sin ejecutor conectado: se muestra como «Solicitada · Pendiente del servidor». Solo se muestra operativa cuando el identificador coincide con el configurado y existe señal de disponibilidad en los últimos 3 minutos. Asignar custodios no concede acceso al panel. Una cuenta de custodia que quede inactiva impide nuevas ejecuciones hasta revisar la política.

### Preparación en el servidor de la aplicación

1. Aplicar migraciones, preparar almacenamiento privado persistente y comprobar una copia con el cliente SQL local. Si la instalación aún no tiene clave, inicializarla una sola vez mediante `crear_respaldo --crear-clave`, comprobar su recuperación y custodiarla; no sustituir una clave existente.
2. Definir en la configuración del servidor y del servicio web el mismo identificador exclusivo y estable, por ejemplo `BACKUP_WORKER_ID=cesfam-servidor`. El identificador no es una contraseña. No iniciar este ejecutor en el Mac de desarrollo contra la base compartida de producción.
3. Con Docker Compose, el servicio opcional `respaldos` comparte exclusivamente los volúmenes privados de copias y claves, recibe `.env`, no publica puertos y no monta el socket de Docker. Debe construirse con el código actualizado. El perfil no se inicia con el despliegue ordinario:

```sh
docker compose -f Docker-compose.yml --profile respaldos up -d --build respaldos
```

Desplegar también el servicio web con la versión actualizada, su configuración y estilos. No hace falta montar estáticos ni media en el ejecutor. La aplicación y el ejecutor deben apuntar al mismo almacenamiento privado y clave para que el panel pueda descargar las copias.

Sin Compose, ejecutar bajo el supervisor de procesos del servidor:

```sh
venv/bin/python manage.py ejecutar_respaldos_programados --continuo
```

Para una comprobación única, omitir `--continuo`. Existe `--cliente-docker` para mantenimiento con cliente oficial compatible ya instalado; el servicio Compose está preparado para usar el cliente SQL del contenedor, sin acceso al motor Docker del host.

4. Revisar en el panel la señal y disponibilidad, completar la política y activar expresamente la programación. No se despliega ni activa el servicio desde el navegador.

### Comportamiento de ejecución

- Comprueba la política cada 60 segundos y genera copias desde el siguiente horario posterior a la activación. No inicia una copia inmediata solo por activar.
- Utiliza `America/Santiago`. En una hora inexistente por cambio de horario, se desplaza al primer minuto válido. Una hora repetida se ejecuta una sola vez, en su primera ocurrencia. Para cada 12 horas se usan dos horas locales separadas por 12 horas de reloj; en un cambio de horario el intervalo real puede variar.
- Coordina ejecutores mediante bloqueo exclusivo de la conexión MySQL/MariaDB. Cada revisión de política y horario tiene una ejecución única. Al recuperar el servicio, procesa únicamente el último horario pendiente, sin acumular copias por todos los horarios perdidos.
- Registra inicio, final, copia generada o fallo sin guardar excepciones con credenciales. Un turno fallido o interrumpido no se reintenta automáticamente; requiere revisión y se mantiene en historial. Una ejecución anterior sin resultado se marca interrumpida cuando un nuevo ejecutor obtiene el bloqueo exclusivo.
- La señal se actualiza entre comprobaciones y al terminar la generación; durante una copia larga puede verse temporalmente sin señal reciente. El panel distingue la ejecución en curso.
- El panel muestra falta de señal, errores recientes y últimos resultados. No se envían alertas externas. Para supervisión continua, el CESFAM debe integrar la revisión del servicio y del almacenamiento a su monitoreo operativo.
- Las copias nuevas siguen pendientes de prueba y traslado a Windows. No hay eliminación automática por conservación ni pruebas de restauración programadas.

Este cambio prepara el código, comando y servicio opcional. Aplicar migraciones no crea una tarea ni inicia un ejecutor; desplegarlo y activar la política son pasos separados. No se han trasladado archivos ni claves a otro equipo.

### Corrección del guardado y estados de activación

El día de la semana y la hora se conservan al cambiar de frecuencia; el día únicamente se aplica a la frecuencia semanal. Manual no programa copias. Los errores de activación aparecen en el mismo formulario y conservan el motivo escrito. La solicitud pendiente no crea copias, no inicia procesos en el equipo de desarrollo y no acredita funcionamiento automático. La frecuencia diaria a las 23:00 de Chile continental fue indicada por el usuario; debe quedar guardada y comprobada en la política del despliegue antes de acreditar su ejecución.

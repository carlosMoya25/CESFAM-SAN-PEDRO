# Auditoría central Implementation Plan

> Ejecución en esta conversación sobre los cambios locales existentes; usar pruebas antes de implementación y revisar el diff final. No crear commits ni desplegar.

**Goal:** Registrar actividad futura de todos los módulos y permitir consulta a Administración y Técnico TI.
**Architecture:** EventoAuditoria + observadores con campos permitidos + middleware HTTP; logging JSON seguro a consola. Se conservan los historiales existentes y las transacciones del negocio.
**Tech Stack:** Django 5.2, Python estándar, MySQL/MariaDB; SQLite aislado para pruebas.
**Spec:** docs/superpowers/specs/2026-10-26-auditoria-design.md

## Restricciones
- Sin dependencias nuevas, sin cuerpos, claves, tokens, IP o consultas de búsqueda.
- Panel de solo lectura para ambos roles y superusuario activo; 25 filas por página.
- Escrituras críticas y su evento en la misma transacción; navegación con diagnóstico independiente en caso de fallo.
- No aplicar migraciones ni activar servicios sobre la base compartida.

## Revisión prioritaria
- Credenciales en formularios, callbacks OAuth y mensajes de excepción: nunca persistirlas.
- Solicitudes consecutivas y logout: no atribuir eventos al usuario anterior.
- Excepciones durante auditoría: no confirmar cambios críticos incompletos.
- QuerySet.update y comandos: conservar referencias a movimientos/ejecuciones y documentar el límite SQL.
- Fechas locales, filtros inválidos y UUID malformado: no ampliar la consulta.

## 1. Persistencia y captura de negocio
- [x] Crear pruebas core/test_auditoria.py para cambios de catálogo, roles, movimientos, privacidad, comandos y rollback; observar el fallo inicial.
- [x] Añadir EventoAuditoria y migración, core/auditoria.py (contexto y persistencia), core/auditoria_signals.py (lista explícita de modelos/campos) y conectar desde CoreConfig.ready.
- [x] Activar ATOMIC_REQUESTS para cubrir también allauth y completar transacciones cortas en registros de respaldo. Verificar las pruebas.

## 2. Accesos y diagnóstico
- [x] Probar login/logout/fallos, 403/404/500, correlación, datos excluidos y errores de almacenamiento.
- [x] Añadir middleware y formateador JSON seguro, configurar LOGGING sin desactivar loggers existentes y rotación del diagnóstico de Docker.
- [x] Identificar comandos sin capturar argumentos ni mensajes privados; verificar las pruebas.

## 3. Panel
- [x] Probar ambos roles, otros usuarios, datos escapados, admin de solo lectura y filtros/paginación.
- [x] Añadir formulario, vistas, rutas, plantillas y enlace del menú reutilizando estilos del proyecto; no añadir exportaciones.
- [x] Ejecutar pruebas y comprobar vistas GET y formularios inválidos.

## 4. Verificación
- [x] Suite Django completa en SQLite aislado y pruebas JS existentes.
- [x] Comprobar migraciones, plantillas, diff y revisión de seguridad de los cambios.
- [x] Documentar operación, límites y migración pendiente; informar resultados y riesgos reales.

## Registro de ejecución

Se implementó en la copia de trabajo conservando los cambios anteriores. La revisión independiente detectó el filtrado de update_fields y las membresías retiradas al borrar grupos; ambos casos tienen pruebas de regresión. Se incluyó borrado masivo de grupos, diagnóstico antes de django.setup y fallos del diagnóstico después del commit. No se aplicaron migraciones a la base compartida ni se desplegó.

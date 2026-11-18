# SIGRI – Sistema de Gestión de Requerimientos Informáticos, Inventario y Farmacia

**Proyecto de Aplicación Práctica de Título (APT)**  
**Ingeniería en Informática – Duoc UC, Sede Melipilla**  
**Año: 2026**

## 1. Nombre y descripción del proyecto

**SIGRI** es un sistema web desarrollado para el CESFAM de San Pedro, cuyo objetivo es centralizar y optimizar la gestión de requerimientos informáticos, el control del inventario institucional y la administración de medicamentos.

### ¿A quién está dirigido?

El sistema está orientado a los funcionarios del CESFAM San Pedro, especialmente al personal de soporte informático, encargados de inventario, encargados de farmacia y administradores.

### ¿Qué problema resuelve?

El proyecto busca solucionar dificultades relacionadas con:

- Falta de trazabilidad y seguimiento de requerimientos informáticos.
- Dificultades para controlar los artículos y movimientos del inventario institucional.
- Falta de visibilidad del stock de medicamentos por anexo.
- Procesos administrativos descentralizados.
- Dificultades para obtener reportes e información consolidada.

### Funcionalidades principales

**Módulo de Requerimientos TI**
- Registro y seguimiento de solicitudes informáticas.
- Asignación y autoasignación de técnicos.
- Actualización de estados de los requerimientos.
- Historial y trazabilidad de solicitudes.

**Módulo de Inventario**
- Administración de artículos y categorías.
- Registro de entradas, salidas y transferencias.
- Control de stock por anexo.
- Historial de movimientos.

**Módulo de Farmacia**
- Registro y administración de medicamentos.
- Control de lotes y fechas de vencimiento.
- Gestión de existencias por anexo.
- Registro de entradas, salidas y traslados.
- Historial de movimientos de medicamentos.

**Administración y reportes**
- Paneles de información y estadísticas.
- Reportes de gestión.
- Administración de usuarios, roles y permisos.

## 2. Tecnologías utilizadas

| Tecnología | Utilización |
|---|---|
| Python 3.12 | Lenguaje principal de programación |
| Django 5.2 | Framework de desarrollo backend |
| MySQL | Base de datos relacional |
| HTML5 | Estructura de interfaces |
| CSS3 | Diseño y presentación visual |
| JavaScript | Interactividad del frontend |
| Django Templates | Renderización de vistas |
| Google OAuth | Autenticación mediante Google |
| Gunicorn | Servidor de aplicaciones |
| Docker | Contenedorización del sistema |
| Traefik | Proxy inverso y acceso HTTPS |
| Git y GitHub | Control de versiones |
| OWASP ZAP | Evaluación de seguridad |

### Seguridad implementada

- Autenticación y control de acceso mediante roles.
- Protección CSRF.
- Protección contra intentos reiterados de inicio de sesión mediante Django Axes.
- Cierre de sesión por inactividad.
- Configuración de cookies seguras y HTTPS.
- Cabeceras de seguridad HTTP.
- Política Content Security Policy (CSP) en evaluación.
- Pruebas de seguridad utilizando OWASP ZAP.

## 3. Instrucciones de ejecución local

### Requisitos previos

- Python 3.12 o compatible.
- MySQL.
- Git.
- pip.
- Entorno virtual de Python.

### Paso 1. Clonar el repositorio

```bash
git clone https://github.com/carlosMoya25/CESFAM-SAN-PEDRO.git
cd CESFAM-SAN-PEDRO
```

### Paso 2. Crear un entorno virtual

```bash
python -m venv venv
```

Activar el entorno virtual:

**macOS / Linux**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### Paso 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4. Configurar la base de datos

Crear una base de datos en MySQL:

```sql
CREATE DATABASE sigri
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Configurar las credenciales de conexión en las variables de entorno utilizadas por Django.

También deben configurarse la clave secreta de Django y las credenciales de autenticación de Google, cuando corresponda.

**Importante:** No incluir contraseñas, claves secretas ni credenciales reales en el repositorio.

### Paso 5. Aplicar migraciones

```bash
python manage.py migrate
```

### Paso 6. Crear un superusuario

```bash
python manage.py createsuperuser
```

### Paso 7. Ejecutar el servidor

```bash
python manage.py runserver
```

Acceder desde el navegador:

http://127.0.0.1:8000/

**Nota:** Para ejecutar el proyecto correctamente, las variables de entorno y la configuración local deben coincidir con las definidas en `settings.py`. El inicio de sesión con Google requiere configurar sus credenciales y URL de redirección autorizadas.

## 4. Integrantes y roles

| Integrante | Rol y responsabilidades |
|---|---|
| Carlos Moya Riquelme | Desarrollo del módulo de inventario, funcionalidades de requerimientos TI, integración y seguridad del sistema. |
| José Tomás Frías | Desarrollo del módulo de farmacia, revisión de autenticación, credenciales y permisos. |
| Ivannia Carrasco Naranjo | Desarrollo del panel técnico de requerimientos, gestión de estados, asignaciones y seguimiento de solicitudes. |

El equipo participó colaborativamente en la planificación, revisión, pruebas e integración de las funcionalidades del proyecto.

## 5. Metodología de trabajo

Para el desarrollo de SIGRI se utilizó una metodología ágil basada en **Scrum**, organizando el trabajo en tres sprints.

### Sprint 1 – Estructura y autenticación

- Diseño inicial de la base de datos.
- Configuración del proyecto Django.
- Implementación de usuarios y autenticación.
- Definición de roles y permisos.

### Sprint 2 – Requerimientos informáticos

- Implementación del registro de requerimientos.
- Desarrollo del panel técnico.
- Asignación y seguimiento de solicitudes.
- Gestión de estados e historial.
- Pruebas funcionales y ajustes.

### Sprint 3 – Inventario y farmacia

- Desarrollo del módulo de inventario.
- Administración de artículos y categorías.
- Implementación de movimientos y control de stock.
- Desarrollo del módulo de farmacia.
- Gestión de medicamentos, lotes y existencias por anexo.
- Integración de módulos y reportes.

### Herramientas de gestión

Se utilizó **Trello** para organizar actividades, historias de usuario, responsables y seguimiento del trabajo.

**Git y GitHub** permitieron administrar versiones, integrar cambios y mantener un historial del desarrollo.

Durante cada sprint se realizaron revisiones, pruebas y ajustes de acuerdo con los avances y la retroalimentación recibida.

## 6. Arquitectura de la solución

SIGRI utiliza una **arquitectura web cliente-servidor**, basada en el patrón Modelo-Vista-Template (MVT) de Django.

### Componentes principales

**Frontend**

Desarrollado con HTML5, CSS3, JavaScript y Django Templates. Permite a los usuarios interactuar con los formularios, paneles y funcionalidades del sistema desde un navegador.

**Backend**

Desarrollado con Python y Django. Administra la lógica de negocio, validaciones, autenticación, permisos y procesamiento de solicitudes.

**Base de datos**

MySQL almacena la información de usuarios, requerimientos, artículos, medicamentos y movimientos.

**Autenticación**

Se integra Google mediante OAuth para permitir el inicio de sesión con cuentas autorizadas, manteniendo los controles de permisos del sistema.

**Infraestructura**

La aplicación se encuentra desplegada en un servidor VPS, utilizando Docker, Gunicorn y Traefik para ejecutar y publicar el servicio mediante HTTPS.

### Diagrama simplificado

```text
             USUARIO
                |
                v
        NAVEGADOR WEB
       HTML / CSS / JS
                |
              HTTPS
                |
                v
          VPS / TRAEFIK
                |
                v
       DJANGO / GUNICORN
                |
      +---------+---------+
      |         |         |
      v         v         v
 Requerimientos Inventario Farmacia
      |         |         |
      +---------+---------+
                |
                v
              MySQL

 Autenticación: Google OAuth
```

### Organización lógica del proyecto

```text
CESFAM-SAN-PEDRO/
|
|-- core/
|-- usuarios/
|-- requerimientos/
|-- inventario/
|-- farmacia/
|-- organizacion/
|
|-- templates/
|-- static/
|-- media/
|
|-- manage.py
|-- requirements.txt
|-- README.md
```

Esta separación por aplicaciones permite mantener los módulos organizados, facilitar el mantenimiento y permitir futuras ampliaciones.

## 7. Acceso al sistema y repositorio

**Sistema web:**  
https://cesfam.liceosp.cl

**Repositorio GitHub:**  
https://github.com/carlosMoya25/CESFAM-SAN-PEDRO

---

**Proyecto SIGRI – APT Ingeniería en Informática – Duoc UC, 2026**

Desarrollado como propuesta tecnológica para mejorar la trazabilidad, organización y eficiencia de los procesos administrativos y operativos del CESFAM San Pedro.

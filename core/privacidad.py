"""Aviso informativo versionado. Cambiar la versión al modificar su contenido."""
import hashlib

VERSION = "2026-10-24.1"
TITULO = "Privacidad y Ley 21.719"
INTRODUCCION = (
    "La Ley 21.719 reforma la protección de datos personales en Chile. Su régimen general "
    "entra en vigencia el 1 de diciembre de 2026. Este aviso explica el alcance de la "
    "información personal en el sistema de gestión del CESFAM San Pedro."
)
SECCIONES = (
    ("Qué información se registra", (
        "El sistema registra nombres, apellidos, correo, teléfono cuando se informa, anexo, "
        "departamento y roles de los usuarios. También vincula a cada funcionario con las "
        "solicitudes, soluciones, movimientos e historiales que genera."
    )),
    ("Para qué se utiliza", (
        "Estos registros permiten identificar a los usuarios, gestionar accesos, atender "
        "requerimientos TI, administrar inventario y farmacia y mantener la trazabilidad "
        "de las operaciones. Cada tratamiento debe contar con una base legal aplicable; "
        "esta constancia de lectura no la sustituye."
    )),
    ("Información que no debes ingresar", (
        "No incluyas contraseñas, tokens, diagnósticos, RUT ni otros antecedentes de pacientes "
        "en títulos, descripciones, observaciones o archivos de importación. El módulo de "
        "farmacia aquí descrito administra existencias y movimientos; este aviso no autoriza "
        "el registro de antecedentes clínicos."
    )),
    ("Acceso y confidencialidad", (
        "El acceso se gestiona mediante cuentas y roles. Utiliza la información únicamente "
        "para tus funciones y no compartas credenciales. Si detectas información expuesta o "
        "un acceso indebido, comunícalo a la administración del sistema por los canales "
        "institucionales disponibles."
    )),
    ("Desvinculación y conservación", (
        "Desactivar una cuenta no elimina sus solicitudes, soluciones ni movimientos. "
        "La conservación de registros y de su autoría debe responder a una finalidad y base "
        "legal, con plazos definidos por la institución. No supone una autorización para "
        "conservar todos los datos indefinidamente."
    )),
    ("Tus derechos", (
        "La reforma contempla derechos de acceso, rectificación, supresión, oposición, "
        "portabilidad y bloqueo, sujetos a sus requisitos y excepciones. Puedes solicitar "
        "orientación a la administración del sistema para identificar al responsable y el "
        "canal institucional de atención. Este aviso no sustituye la política institucional: "
        "deben completarse la identificación del responsable, el contacto de atención, las "
        "bases legales y los plazos de conservación antes de utilizarlo como política formal."
    )),
    ("Qué significa confirmar la lectura", (
        "La confirmación es voluntaria y no condiciona el acceso al sistema. Solo registra "
        "que declaras haber leído este aviso; no autoriza tratamientos opcionales, no "
        "implica renunciar a derechos y no certifica el cumplimiento de la ley. Si un "
        "tratamiento requiere consentimiento, deberá solicitarse por separado con una "
        "finalidad específica y un mecanismo para revocarlo."
    )),
    ("Registro de esta constancia", (
        "Si confirmas, se guardarán tu identificador de usuario, la fecha y hora, la versión "
        "y una copia del aviso y de tu declaración, junto con una huella del contenido. "
        "No se recopila tu dirección IP para esta constancia."
    )),
)
DECLARACION = "He leído y comprendido este aviso sobre privacidad y el alcance de esta constancia."
FUENTE = "https://www.bcn.cl/leychile/Navegar?idNorma=1209272&idVersion=2026-12-01"
TEXTO = "\n\n".join([TITULO, INTRODUCCION] + [f"{titulo}\n{texto}" for titulo, texto in SECCIONES] + [FUENTE])
HUELLA = hashlib.sha256((TEXTO + "\n\n" + DECLARACION).encode("utf-8")).hexdigest()

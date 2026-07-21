"""
Configuración del webhook de WhatsApp Cloud API.

Los secretos viven ÚNICAMENTE en variables de entorno (nunca en la base de datos,
nunca en el repositorio). La configuración no secreta de cada línea vive en la tabla
`whatsapp_lines`.

Nombres de las variables
------------------------
El documento de arquitectura (§3) define una **aplicación de Meta separada** para
WhatsApp, distinta de la de Lead Ads. Como `META_APP_SECRET` y `META_VERIFY_TOKEN`
ya están tomados por los webhooks de Lead Ads (UNPO y NORA, en `routers/leads.py`),
este módulo usa nombres propios con el prefijo del módulo, siguiendo la convención
del proyecto (`NORA_META_VERIFY_TOKEN` para NORA):

    WHATSAPP_VERIFY_TOKEN     -> handshake GET del webhook
    WHATSAPP_META_APP_SECRET  -> firma X-Hub-Signature-256 del POST

Las lecturas son en tiempo de llamada (no en tiempo de import) para que el entorno
se pueda cambiar sin reimportar el módulo (tests, rotación de secretos en Render).
"""

import os

# Nombres de las variables de entorno (única fuente de verdad; los tests los reusan).
VERIFY_TOKEN_ENV = "WHATSAPP_VERIFY_TOKEN"
APP_SECRET_ENV = "WHATSAPP_META_APP_SECRET"

# Proveedor de mensajería de este módulo (columna `provider` de las tablas whatsapp_*).
PROVIDER = "meta"

# Límite de tamaño del cuerpo aceptado en el POST del webhook. Meta envía payloads
# chicos (unos pocos KB); 1 MiB es holgado y evita que un cuerpo enorme consuma
# memoria del proceso. Es una protección LOCAL de este endpoint: el proyecto no
# tiene middleware global de tamaño máximo y no se agrega uno para no alterar el
# resto de la API (subida de imágenes de productos, importadores de Excel).
MAX_WEBHOOK_BODY_BYTES = 1 * 1024 * 1024

# Retención del payload crudo (`raw_payload_expires_at`). El barrido de expirados
# es responsabilidad de una etapa posterior; acá solo se marca el vencimiento.
RAW_PAYLOAD_RETENTION_DAYS = 30


def get_verify_token() -> str:
    """Verify token del handshake GET. Cadena vacía si no está configurado."""
    return (os.getenv(VERIFY_TOKEN_ENV) or "").strip()


def get_app_secret() -> str:
    """App Secret usado para validar la firma del POST. Vacío si no está configurado."""
    return (os.getenv(APP_SECRET_ENV) or "").strip()

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
# lo hace el comando de purga (Etapa 1D); acá solo se marca el vencimiento.
RAW_PAYLOAD_RETENTION_DAYS = 30

# ---------------------------------------------------------------------------
# Etapa 1D — reprocesamiento de eventos y purga de payloads.
# ---------------------------------------------------------------------------
# Variables de entorno del reprocesador. Los valores por defecto son SEGUROS para
# DESARROLLO; en producción se ajustan por entorno al programar el cron (ver la doc).
LEASE_SECONDS_ENV = "WHATSAPP_REPROCESS_LEASE_SECONDS"
BATCH_SIZE_ENV = "WHATSAPP_REPROCESS_BATCH_SIZE"
MAX_ATTEMPTS_ENV = "WHATSAPP_REPROCESS_MAX_ATTEMPTS"

# Lease del reclamo. Un evento en `processing` se considera ATASCADO si su
# `processing_started_at` es anterior a `now - LEASE_SECONDS`. También se usa como
# "gracia" del `pending`: un `pending` solo es elegible si es más viejo que este
# umbral (un webhook recién recibido se marca en milisegundos; no debe robarse).
DEFAULT_LEASE_SECONDS = 300          # 5 minutos
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_ATTEMPTS = 8             # 1 intento del webhook + hasta 7 reintentos

# Cotas duras para los parámetros de línea de comandos (validación de rango).
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 10_000
MIN_LEASE_SECONDS = 1
MAX_LEASE_SECONDS = 86_400           # 24 h

# Backoff determinístico por número de intento (segundos). Índice = attempt_count del
# intento que acaba de fallar; a partir del último tramo se aplica el tope.
BACKOFF_SCHEDULE_SECONDS = (60, 300, 900, 3600, 21600)   # 1m, 5m, 15m, 1h, 6h
BACKOFF_MAX_SECONDS = BACKOFF_SCHEDULE_SECONDS[-1]


def _get_int(env_name: str, default: int, minimum: int, maximum: int) -> int:
    """Lee un entero de entorno acotado a [minimum, maximum]; si es inválido, default."""
    raw = os.getenv(env_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def get_lease_seconds() -> int:
    return _get_int(LEASE_SECONDS_ENV, DEFAULT_LEASE_SECONDS, MIN_LEASE_SECONDS, MAX_LEASE_SECONDS)


def get_batch_size() -> int:
    return _get_int(BATCH_SIZE_ENV, DEFAULT_BATCH_SIZE, MIN_BATCH_SIZE, MAX_BATCH_SIZE)


def get_max_attempts() -> int:
    # Al menos 1: si fuese 0 no se reintentaría nada y todo quedaría exhausted de entrada.
    return _get_int(MAX_ATTEMPTS_ENV, DEFAULT_MAX_ATTEMPTS, 1, 1000)


def backoff_seconds(attempt_count: int) -> int:
    """
    Segundos de espera antes del próximo reintento, en función del intento que falló.

    Determinística, centralizada y con tope. `attempt_count` es el valor tras el claim
    (1-based): el 1er intento fallido espera `BACKOFF_SCHEDULE_SECONDS[0]`, etc. Todo
    intento igual o mayor al último tramo usa `BACKOFF_MAX_SECONDS`.
    """
    if attempt_count < 1:
        attempt_count = 1
    idx = min(attempt_count - 1, len(BACKOFF_SCHEDULE_SECONDS) - 1)
    return BACKOFF_SCHEDULE_SECONDS[idx]


def get_verify_token() -> str:
    """Verify token del handshake GET. Cadena vacía si no está configurado."""
    return (os.getenv(VERIFY_TOKEN_ENV) or "").strip()


def get_app_secret() -> str:
    """App Secret usado para validar la firma del POST. Vacío si no está configurado."""
    return (os.getenv(APP_SECRET_ENV) or "").strip()


# ---------------------------------------------------------------------------
# Etapa 1I.1 — envío saliente (feature flag).
# ---------------------------------------------------------------------------
# Interruptor del envío saliente de mensajes. Default: APAGADO. Con el flag apagado el
# endpoint de envío responde 503 y NO crea ninguna fila. En 1I.1 NO hay cliente real de
# Meta ni access token: el flag existe para poder integrar el núcleo sin exponer envío.
OUTBOUND_ENABLED_ENV = "WHATSAPP_OUTBOUND_ENABLED"

# Valores considerados "encendido" (lectura en tiempo de llamada, como el resto del módulo).
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def outbound_enabled() -> bool:
    """¿Está habilitado el envío saliente? Lee `WHATSAPP_OUTBOUND_ENABLED` (default false)."""
    return (os.getenv(OUTBOUND_ENABLED_ENV) or "").strip().lower() in _TRUTHY

"""
Normalización del payload de Meta y claves de idempotencia determinísticas.

Este módulo es **puro**: no toca la base de datos ni el entorno. Convierte el JSON
del webhook en estructuras planas que el procesador consume, y calcula las claves de
deduplicación.

Claves de idempotencia
----------------------
Meta **no** garantiza un identificador único a nivel de webhook (el envelope solo
trae `entry[].id` y `entry[].time`, que se repiten entre eventos distintos). Por eso
`event_key` se calcula como un **hash determinístico del contenido**:

    payload_hash = sha256(json canónico del payload)     -> whatsapp_webhook_events.payload_hash
    event_key    = "sha256:<payload_hash>"               -> whatsapp_webhook_events.event_key

Propiedades: mismo reintento de Meta => misma clave => dedupe; eventos distintos =>
claves distintas. No se usa timestamp de recepción ni UUID aleatorio (ninguno de los
dos deduplica un reintento).

Los estados usan su propia clave estable por (mensaje, estado, timestamp), porque un
mismo webhook puede reenviar el mismo estado dentro de payloads distintos.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...schemas_whatsapp import WhatsAppWebhookEnvelope

# Objeto de webhook que corresponde a WhatsApp Cloud API.
SUPPORTED_OBJECT = "whatsapp_business_account"
# `changes[].field` soportado.
SUPPORTED_FIELD = "messages"
# Tipos de mensaje entrante soportados en esta etapa (§10 del plan 1C).
SUPPORTED_MESSAGE_TYPES = frozenset({"text"})
# Estados de mensaje saliente soportados.
SUPPORTED_STATUSES = frozenset({"sent", "delivered", "read", "failed"})

_STATUS_EVENT_KEY_MAX = 255

# Largos REALES de las columnas VARCHAR del esquema (backend/app/models.py). PostgreSQL
# los hace cumplir (error 22001 `StringDataRightTruncation`) mientras que SQLite los
# ignora: sin este acotado, un payload con un campo desmedido dejaría el evento en
# `failed` y perdería el mensaje. No se "arregla" con una migración: el código se adapta
# al esquema aprobado.
MAX_EXTERNAL_ID_LEN = 255      # whatsapp_messages.external_message_id / context_...
MAX_IDENTIFIER_LEN = 255       # whatsapp_contact_identifiers.identifier_value
MAX_DISPLAY_NAME_LEN = 255     # whatsapp_contacts.display_name

# Motivos por los que un elemento no se procesa (se reportan y se logean).
REASON_UNSUPPORTED_MESSAGE_TYPE = "unsupported_message_type"
REASON_MISSING_EXTERNAL_ID = "missing_external_id"
REASON_OVERSIZED_EXTERNAL_ID = "oversized_external_id"
REASON_INVALID_SENDER_IDENTIFIER = "invalid_sender_identifier"


def strip_nul(value):
    """
    Quita el carácter NUL de una cadena.

    PostgreSQL lo rechaza tanto en `text` como en `jsonb` (`unsupported Unicode escape
    sequence`), mientras que SQLite lo acepta: un payload firmado con `\\u0000` haría
    fallar el INSERT del evento y Meta reintentaría indefinidamente el mismo webhook.
    """
    if isinstance(value, str) and "\x00" in value:
        return value.replace("\x00", "")
    return value


def sanitize_payload_for_storage(payload):
    """Copia del payload sin caracteres NUL, apta para la columna JSONB.

    El `payload_hash` / `event_key` se calculan sobre el payload ORIGINAL, así que la
    idempotencia no cambia: esto solo afecta lo que se almacena.
    """
    if isinstance(payload, str):
        return strip_nul(payload)
    if isinstance(payload, dict):
        return {strip_nul(k): sanitize_payload_for_storage(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload_for_storage(v) for v in payload]
    return payload


# --------------------------------------------------------------------------- #
# Estructuras normalizadas
# --------------------------------------------------------------------------- #
@dataclass
class NormalizedMessage:
    """Mensaje entrante normalizado. `supported=False` => no se crea registro."""
    external_id: Optional[str]
    wa_id: Optional[str]
    profile_name: Optional[str]
    message_type: str
    text_body: Optional[str]
    provider_timestamp: Optional[datetime]
    context_external_id: Optional[str]
    supported: bool
    unsupported_reason: Optional[str] = None


@dataclass
class NormalizedStatus:
    """Estado de un mensaje saliente. `event_key` es la clave de dedupe."""
    external_message_id: Optional[str]
    status: Optional[str]
    provider_timestamp: Optional[datetime]
    recipient_id: Optional[str]
    error_code: Optional[str]
    error_title: Optional[str]
    event_key: Optional[str]
    supported: bool


@dataclass
class NormalizedChange:
    """Un `changes[]` ya resuelto: a qué línea apunta y qué elementos trae."""
    field_name: Optional[str]
    phone_number_id: Optional[str]
    messages: List[NormalizedMessage] = field(default_factory=list)
    statuses: List[NormalizedStatus] = field(default_factory=list)
    supported_field: bool = False


@dataclass
class NormalizedEvent:
    """Evento completo normalizado, listo para persistir y procesar."""
    object_type: Optional[str]
    event_type: str
    event_key: str
    payload_hash: str
    changes: List[NormalizedChange] = field(default_factory=list)
    supported_object: bool = False

    @property
    def total_messages(self) -> int:
        return sum(len(c.messages) for c in self.changes)

    @property
    def total_statuses(self) -> int:
        return sum(len(c.statuses) for c in self.changes)


# --------------------------------------------------------------------------- #
# Claves determinísticas
# --------------------------------------------------------------------------- #
def canonical_payload_hash(payload: Any) -> str:
    """
    sha256 hexadecimal de la representación canónica del payload.

    Canónica = JSON con claves ordenadas y sin espacios, de modo que dos entregas del
    mismo evento con distinto orden de claves produzcan el mismo hash.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_event_key(payload_hash: str) -> str:
    """Clave de dedupe del webhook (cabe en `whatsapp_webhook_events.event_key`)."""
    return f"sha256:{payload_hash}"


def build_status_event_key(external_message_id: Optional[str], status: Optional[str],
                           raw_timestamp: Any) -> Optional[str]:
    """
    Clave estable de un evento de estado: (mensaje externo, estado, timestamp de Meta).

    Reenviar el mismo estado en otro webhook produce la misma clave y por lo tanto no
    duplica historial. Si la concatenación excediera el largo de la columna se usa un
    hash del mismo contenido (sigue siendo determinística).
    """
    if not external_message_id or not status:
        return None
    ts = "" if raw_timestamp is None else strip_nul(str(raw_timestamp))
    raw = f"meta:{external_message_id}:{status}:{ts}"
    if len(raw) <= _STATUS_EVENT_KEY_MAX:
        return raw
    return f"meta:sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


# --------------------------------------------------------------------------- #
# Helpers de normalización
# --------------------------------------------------------------------------- #
def parse_provider_timestamp(value: Any) -> Optional[datetime]:
    """
    Convierte el timestamp de Meta (segundos unix, normalmente string) a datetime UTC.
    Devuelve None ante valores ausentes o no numéricos (no rompe el procesamiento).
    """
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(str(value).strip()), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def normalize_wa_id_to_e164(wa_id: Optional[str]) -> Optional[str]:
    """
    Deriva un teléfono E.164 a partir del `wa_id` cuando es seguro hacerlo.

    Meta entrega el `wa_id` como número internacional sin `+`. Solo se normaliza si es
    íntegramente numérico y de largo plausible; si no, se devuelve None y el contacto
    queda identificado únicamente por `wa_id` (identificador estable y preferido).
    """
    if not wa_id:
        return None
    digits = str(wa_id).strip()
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit() or not (8 <= len(digits) <= 15):
        return None
    return f"+{digits}"


def _profile_name_by_wa_id(value) -> Dict[str, str]:
    """Mapa wa_id -> nombre de perfil declarado en `value.contacts[]`."""
    names: Dict[str, str] = {}
    for contact in (value.contacts or []):
        if contact.wa_id and contact.profile and contact.profile.name:
            # La clave se normaliza igual que el `from` del mensaje (sin NUL), o el
            # cruce entre `contacts[]` y `messages[]` no encontraría el perfil.
            names[strip_nul(str(contact.wa_id))] = contact.profile.name
    return names


def _normalize_message(msg, profile_names: Dict[str, str]) -> NormalizedMessage:
    """
    Normaliza un mensaje entrante y decide si es procesable.

    Los campos que van a columnas VARCHAR se acotan explícitamente:
      - `display_name` se TRUNCA (es cosmético);
      - un id externo o un `wa_id` fuera de largo NO se truncan (romperían la
        idempotencia y la identidad): el elemento se marca como no soportado;
      - un `context` fuera de largo se descarta (es metadato opcional) y el mensaje
        se procesa igual.
    """
    msg_type = (msg.type or "").strip().lower()
    tipo_soportado = msg_type in SUPPORTED_MESSAGE_TYPES

    external_id = strip_nul(msg.id) if msg.id else None
    wa_id = strip_nul(msg.from_) if msg.from_ else None
    profile_name = profile_names.get(str(wa_id)) if wa_id else None
    if profile_name:
        profile_name = strip_nul(profile_name)[:MAX_DISPLAY_NAME_LEN]

    context_external_id = strip_nul(msg.context.id) if (msg.context and msg.context.id) else None
    if context_external_id and len(context_external_id) > MAX_EXTERNAL_ID_LEN:
        context_external_id = None

    reason = None
    if not tipo_soportado:
        reason = REASON_UNSUPPORTED_MESSAGE_TYPE
    elif not external_id:
        reason = REASON_MISSING_EXTERNAL_ID
    elif len(external_id) > MAX_EXTERNAL_ID_LEN:
        reason = REASON_OVERSIZED_EXTERNAL_ID
    elif wa_id and len(wa_id) > MAX_IDENTIFIER_LEN:
        reason = REASON_INVALID_SENDER_IDENTIFIER

    return NormalizedMessage(
        external_id=external_id,
        wa_id=wa_id,
        profile_name=profile_name,
        message_type=msg_type or "unknown",
        text_body=(strip_nul(msg.text.body) if (tipo_soportado and msg.text) else None),
        provider_timestamp=parse_provider_timestamp(msg.timestamp),
        context_external_id=context_external_id,
        supported=(reason is None),
        unsupported_reason=reason,
    )


def _normalize_status(st) -> NormalizedStatus:
    status = (st.status or "").strip().lower()
    external_id = strip_nul(st.id) if st.id else None
    error_code = None
    error_title = None
    if st.errors:
        first = st.errors[0]
        # `error_code` va a VARCHAR(64) y `error_title` a un campo sanitizado.
        error_code = None if first.code is None else strip_nul(str(first.code))[:64]
        error_title = (first.title or None)
        if error_title:
            error_title = " ".join(strip_nul(str(error_title)).split())[:200]
    return NormalizedStatus(
        external_message_id=external_id,
        status=status or None,
        provider_timestamp=parse_provider_timestamp(st.timestamp),
        recipient_id=strip_nul(st.recipient_id) if st.recipient_id else None,
        error_code=error_code,
        error_title=error_title,
        event_key=build_status_event_key(external_id, status, st.timestamp),
        supported=bool(status in SUPPORTED_STATUSES and external_id),
    )


def normalize_envelope(payload: Any) -> NormalizedEvent:
    """
    Normaliza el payload crudo del webhook.

    Tolerante por diseño: si el envelope no valida (o no es un objeto), se devuelve un
    evento sin cambios y `supported_object=False`; el webhook se persiste igual y se
    marca como ignorado, en vez de romper la recepción.
    """
    payload_hash = canonical_payload_hash(payload)
    event_key = build_event_key(payload_hash)

    if not isinstance(payload, dict):
        return NormalizedEvent(
            object_type=None, event_type="invalid", event_key=event_key,
            payload_hash=payload_hash, changes=[], supported_object=False,
        )

    try:
        envelope = WhatsAppWebhookEnvelope.model_validate(payload)
    except Exception:  # noqa: BLE001 — un envelope ilegible no debe romper el webhook
        return NormalizedEvent(
            object_type=None, event_type="invalid", event_key=event_key,
            payload_hash=payload_hash, changes=[], supported_object=False,
        )

    object_type = envelope.object_
    supported_object = (object_type == SUPPORTED_OBJECT)

    changes: List[NormalizedChange] = []
    fields_seen: List[str] = []

    for entry in (envelope.entry or []):
        for change in (entry.changes or []):
            field_name = change.field
            if field_name:
                fields_seen.append(field_name)
            value = change.value
            if value is None:
                changes.append(NormalizedChange(
                    field_name=field_name, phone_number_id=None,
                    supported_field=(field_name == SUPPORTED_FIELD),
                ))
                continue

            profile_names = _profile_name_by_wa_id(value)
            normalized = NormalizedChange(
                field_name=field_name,
                phone_number_id=(value.metadata.phone_number_id if value.metadata else None),
                supported_field=(field_name == SUPPORTED_FIELD),
            )
            if supported_object and normalized.supported_field:
                normalized.messages = [_normalize_message(m, profile_names)
                                       for m in (value.messages or [])]
                normalized.statuses = [_normalize_status(s) for s in (value.statuses or [])]
            changes.append(normalized)

    # `event_type` es informativo (columna String(64)): el `field` del evento o el
    # objeto recibido cuando no es de WhatsApp.
    if fields_seen:
        event_type = fields_seen[0][:64]
    elif object_type:
        event_type = str(object_type)[:64]
    else:
        event_type = "unknown"

    return NormalizedEvent(
        object_type=object_type,
        event_type=event_type,
        event_key=event_key,
        payload_hash=payload_hash,
        changes=changes,
        supported_object=supported_object,
    )

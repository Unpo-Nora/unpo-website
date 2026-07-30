"""
Núcleo transaccional del envío saliente de texto (Etapa 1I.1).

Este módulo NO llama a Meta. Resuelve todo lo local y seguro del envío:
  - texto canónico y validación (CRLF→LF, no vacío, ≤4096);
  - resolución del destinatario a partir de los identificadores del contacto
    (jamás la línea, el phone_masked, el nombre, ni el teléfono del lead/vendedor);
  - ventana de atención de 24 h;
  - idempotencia por `client_request_id` (autoridad ÚNICA, viene en el body);
  - "una salida en vuelo por conversación" bajo lock `SELECT ... FOR UPDATE`;
  - reserva del mensaje `pending` → transición `sending` ANTES de invocar al sender;
  - aplicación del resultado con compare-and-set (sin retroceder estados).

Separación sync/async: la parte de base de datos es SÍNCRONA (`reserve_outbound`,
`apply_result`); el sender (async, red en 1I.2) se invoca DESDE EL ENDPOINT, entre ambas,
para no mantener una transacción abierta durante la llamada externa. Esto también permite
testear la concurrencia real (FOR UPDATE) llamando a `reserve_outbound` desde hilos.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from . import inbox as svc
from .config import PROVIDER
from .processor import next_current_status
from .redaction import safe_error, short_key
from .sender import (
    OUTCOME_ACCEPTED,
    OUTCOME_AMBIGUOUS,
    SendResult,
    SendTextCommand,
)

logger = logging.getLogger("uvicorn.error")

# --- Constantes de dominio ---------------------------------------------------
DIRECTION_OUTBOUND = "outbound"
MESSAGE_TYPE_TEXT = "text"
ORIGIN_CRM = "crm"

STATUS_PENDING = "pending"
STATUS_SENDING = "sending"
STATUS_ACCEPTED = "accepted"
STATUS_UNKNOWN = "unknown"
STATUS_FAILED = "failed"

# Estados que cuentan como "una salida en vuelo" y bloquean un nuevo envío.
IN_FLIGHT_STATES = ("pending", "sending", "unknown")

MAX_TEXT_LENGTH = 4096
WINDOW_MARGIN = timedelta(seconds=60)

_WA_ID = "wa_id"
_PHONE_E164 = "phone_e164"

# --- Códigos de error ESTABLES del contrato (nunca detalle crudo de Meta) ----
CODE_DISABLED = "WHATSAPP_OUTBOUND_DISABLED"
CODE_NOT_FOUND = "WHATSAPP_CONVERSATION_NOT_FOUND"
CODE_LINE_INACTIVE = "WHATSAPP_LINE_INACTIVE"
CODE_FORBIDDEN = "WHATSAPP_SEND_FORBIDDEN"
CODE_TEXT_EMPTY = "WHATSAPP_TEXT_EMPTY"
CODE_TEXT_TOO_LONG = "WHATSAPP_TEXT_TOO_LONG"
CODE_UNSUPPORTED_TYPE = "WHATSAPP_UNSUPPORTED_MESSAGE_TYPE"
CODE_TEMPLATE_REQUIRED = "WHATSAPP_TEMPLATE_REQUIRED"
CODE_RECIPIENT_UNAVAILABLE = "WHATSAPP_RECIPIENT_UNAVAILABLE"
CODE_IN_PROGRESS = "WHATSAPP_SEND_IN_PROGRESS"
CODE_MISMATCH = "WHATSAPP_IDEMPOTENCY_MISMATCH"
CODE_INTERNAL = "WHATSAPP_OUTBOUND_INTERNAL"


class OutboundError(Exception):
    """Error de envío con código estable y status HTTP. El `message` es genérico y no
    filtra datos (ni del destinatario ni de una conversación ajena)."""

    def __init__(self, http_status: int, code: str, message: str = ""):
        super().__init__(code)
        self.http_status = http_status
        self.code = code
        self.message = message or code


@dataclass
class Reserved:
    """El mensaje quedó reservado y en `sending`: hay que invocar al sender."""
    message_id: int
    command: SendTextCommand


@dataclass
class Replay:
    """Replay idempotente: el `client_request_id` ya existía y coincide; NO se reenvía."""
    message: models.WhatsAppMessage


# --------------------------------------------------------------------------- #
# Texto canónico
# --------------------------------------------------------------------------- #
def canonicalize_text(raw: Optional[str]) -> str:
    """CRLF y CR → LF. NO elimina saltos ni espacios internos. Representación única que se
    persiste y con la que se compara la idempotencia."""
    if raw is None:
        return ""
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def is_blank(canonical: str) -> bool:
    return canonical.strip() == ""


# --------------------------------------------------------------------------- #
# Resolución del destinatario (solo identificadores del contacto)
# --------------------------------------------------------------------------- #
def _valid_wa_id(value: str) -> bool:
    return bool(value) and value.isdigit() and 8 <= len(value) <= 15


def _valid_phone_e164(value: str) -> bool:
    return bool(value) and value.startswith("+") and value[1:].isdigit() and 8 <= len(value[1:]) <= 15


def resolve_meta_recipient(db: Session, contact_id: int) -> Optional[str]:
    """
    Destinatario Meta del contacto, en orden ESTRICTO de preferencia:

        1) wa_id primario · 2) wa_id · 3) phone_e164 primario · 4) phone_e164

    Valida el formato básico SIN modificar el valor. Devuelve el primero con formato
    válido, o None si no hay ninguno. NUNCA usa el display_number de la línea, el
    phone_masked, el nombre del contacto ni el teléfono del lead/vendedor.
    """
    I = models.WhatsAppContactIdentifier
    rows = (
        db.query(I.identifier_type, I.identifier_value, I.is_primary)
        .filter(
            I.contact_id == contact_id,
            I.provider == PROVIDER,
            I.identifier_type.in_([_WA_ID, _PHONE_E164]),
        )
        .all()
    )

    def pick(itype: str, primary: bool) -> Optional[str]:
        for t, v, p in rows:
            if t == itype and bool(p) == primary:
                return v
        return None

    for itype, primary, validator in (
        (_WA_ID, True, _valid_wa_id),
        (_WA_ID, False, _valid_wa_id),
        (_PHONE_E164, True, _valid_phone_e164),
        (_PHONE_E164, False, _valid_phone_e164),
    ):
        value = pick(itype, primary)
        if value is not None and validator(value):
            return value
    return None


# --------------------------------------------------------------------------- #
# Ventana de atención
# --------------------------------------------------------------------------- #
def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normaliza a aware-UTC. SQLite devuelve naive aunque la columna sea tz-aware."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def window_open(conv: models.WhatsAppConversation, now: datetime) -> bool:
    """Ventana abierta si `now_utc < customer_service_window_expires_at - 60s`. Si el
    campo es NULL (sin inbound conocido) se considera CERRADA (fail-closed)."""
    expires = _as_utc(conv.customer_service_window_expires_at)
    if expires is None:
        return False
    return _as_utc(now) < expires - WINDOW_MARGIN


# --------------------------------------------------------------------------- #
# Permisos de envío por línea
# --------------------------------------------------------------------------- #
def line_can_send(db: Session, user: models.User, line: models.WhatsAppLine) -> bool:
    """Admin: siempre. Vendedor: solo con `can_send=True` explícito en la línea (la
    asignación por sí sola NO concede can_send)."""
    if svc.is_admin(user):
        return True
    row = (
        db.query(models.WhatsAppLineUserAccess.id)
        .filter(
            models.WhatsAppLineUserAccess.user_id == user.id,
            models.WhatsAppLineUserAccess.line_id == line.id,
            models.WhatsAppLineUserAccess.can_send.is_(True),
        )
        .first()
    )
    return row is not None


# --------------------------------------------------------------------------- #
# Idempotencia
# --------------------------------------------------------------------------- #
def _replay_or_mismatch(
    db: Session, existing: models.WhatsAppMessage, conversation_id: int, canonical: str
) -> Replay:
    """Con un `client_request_id` ya existente: replay si coincide (misma conversación,
    tipo text, mismo texto canónico) o 409 mismatch en cualquier otro caso. El mismatch
    responde igual sea cual sea la causa: NO filtra info de una conversación ajena."""
    same = (
        existing.conversation_id == conversation_id
        and existing.message_type == MESSAGE_TYPE_TEXT
        and (existing.text_body or "") == canonical
    )
    # Ni el replay ni el mismatch escriben: se libera el lock de la conversación.
    db.rollback()
    if not same:
        raise OutboundError(409, CODE_MISMATCH, "client_request_id ya usado con otro contenido")
    return Replay(message=existing)


# --------------------------------------------------------------------------- #
# Reserva (parte SÍNCRONA; el sender se invoca después, fuera de transacción)
# --------------------------------------------------------------------------- #
def reserve_outbound(
    db: Session,
    user: models.User,
    conversation_id: int,
    *,
    message_type: str,
    text: str,
    client_request_id: uuid.UUID,
    now: Optional[datetime] = None,
) -> Union[Reserved, Replay]:
    """
    Valida, autoriza, aplica idempotencia y reserva el mensaje saliente.

    Devuelve `Reserved` (hay que invocar al sender) o `Replay` (idempotente, no reenviar).
    Lanza `OutboundError` en cualquier rechazo. NO llama a Meta.
    """
    now = now or datetime.now(timezone.utc)

    # 1) Tipo + texto canónico (barato; antes de tocar la base).
    if message_type != MESSAGE_TYPE_TEXT:
        raise OutboundError(422, CODE_UNSUPPORTED_TYPE, "Solo se admite texto")
    canonical = canonicalize_text(text)
    if is_blank(canonical):
        raise OutboundError(422, CODE_TEXT_EMPTY, "El texto no puede estar vacío")
    if len(canonical) > MAX_TEXT_LENGTH:
        raise OutboundError(422, CODE_TEXT_TOO_LONG, "El texto excede el máximo permitido")

    # 2) IDOR: 404 sin filtrar existencia (política vigente) ANTES del lock.
    if svc.get_authorized_conversation(db, user, conversation_id) is None:
        raise OutboundError(404, CODE_NOT_FOUND, "Conversación no encontrada")

    # 3) Recargar/bloquear la conversación (FOR UPDATE) y REVALIDAR autorización.
    C = models.WhatsAppConversation
    conv = db.query(C).filter(C.id == conversation_id).with_for_update().first()
    if conv is None or not svc.can_access_conversation(db, user, conv):
        db.rollback()
        raise OutboundError(404, CODE_NOT_FOUND, "Conversación no encontrada")

    # 4) Línea activa.
    line = db.query(models.WhatsAppLine).filter(models.WhatsAppLine.id == conv.line_id).first()
    if line is None or not line.is_active:
        db.rollback()
        raise OutboundError(409, CODE_LINE_INACTIVE, "La línea no está activa")

    # 5) can_send efectivo.
    if not line_can_send(db, user, line):
        db.rollback()
        raise OutboundError(403, CODE_FORBIDDEN, "No tiene permiso de envío en esta línea")

    M = models.WhatsAppMessage

    # 6) Idempotencia por client_request_id (replay o mismatch).
    existing = db.query(M).filter(M.client_request_id == client_request_id).first()
    if existing is not None:
        return _replay_or_mismatch(db, existing, conv.id, canonical)

    # 7) Ventana de atención (backend valida; no confía en el frontend).
    if not window_open(conv, now):
        db.rollback()
        raise OutboundError(409, CODE_TEMPLATE_REQUIRED, "Fuera de la ventana de atención de 24h")

    # 8) Destinatario (solo identificadores del contacto).
    recipient = resolve_meta_recipient(db, conv.contact_id)
    if recipient is None:
        db.rollback()
        raise OutboundError(409, CODE_RECIPIENT_UNAVAILABLE, "El contacto no tiene destinatario válido")

    # 9) Una salida en vuelo por conversación (dentro de la sección crítica del lock).
    inflight = (
        db.query(M.id)
        .filter(
            M.conversation_id == conv.id,
            M.direction == DIRECTION_OUTBOUND,
            M.current_status.in_(IN_FLIGHT_STATES),
        )
        .first()
    )
    if inflight is not None:
        db.rollback()
        raise OutboundError(409, CODE_IN_PROGRESS, "Ya hay un envío en curso en esta conversación")

    phone_number_id = line.phone_number_id  # sensible: va al sender, nunca a la respuesta

    # 10) Reserva `pending` + commit corto (libera el lock de la conversación).
    msg = M(
        conversation_id=conv.id,
        provider=PROVIDER,
        direction=DIRECTION_OUTBOUND,
        message_type=MESSAGE_TYPE_TEXT,
        text_body=canonical,
        current_status=STATUS_PENDING,
        origin=ORIGIN_CRM,
        client_request_id=client_request_id,
        sender_user_id=user.id,
    )
    db.add(msg)
    try:
        db.commit()
    except IntegrityError:
        # Carrera por el unique parcial de client_request_id (misma crid, conv distinta o
        # ventana estrecha). Re-resolver como replay/mismatch sobre la fila ya existente.
        db.rollback()
        existing = db.query(M).filter(M.client_request_id == client_request_id).first()
        if existing is None:
            raise
        return _replay_or_mismatch(db, existing, conversation_id, canonical)

    message_id = msg.id

    # 11) Transición compare-and-set pending → sending (transacción corta propia).
    locked = (
        db.query(M)
        .filter(M.id == message_id, M.current_status == STATUS_PENDING)
        .with_for_update()
        .first()
    )
    if locked is not None:
        locked.current_status = STATUS_SENDING
        db.commit()

    logger.info(
        "[whatsapp-outbound] reservado message_id=%s conversation_id=%s line_id=%s "
        "user_id=%s crid=%s",
        message_id, conv.id, line.id, user.id, short_key(str(client_request_id), 8),
    )

    command = SendTextCommand(
        internal_message_id=message_id,
        phone_number_id=phone_number_id,
        recipient=recipient,
        text=canonical,
    )
    return Reserved(message_id=message_id, command=command)


# --------------------------------------------------------------------------- #
# Aplicación del resultado (protección ante resultados tardíos)
# --------------------------------------------------------------------------- #
def apply_result(db: Session, message_id: int, result: SendResult) -> models.WhatsAppMessage:
    """
    Aplica el resultado del sender al mensaje reservado, recargándolo BAJO lock.

    Compare-and-set con la precedencia central (`processor.next_current_status`): nunca
    retrocede `sent/delivered/read` ni pisa un terminal de entrega con `accepted`/`failed`.
    Un `unknown` solo se aplica si el mensaje sigue en `pending`/`sending` (nunca degrada
    un estado ya avanzado). NO reintenta: `unknown` queda como estado final local.
    """
    M = models.WhatsAppMessage
    msg = db.query(M).filter(M.id == message_id).with_for_update().first()
    if msg is None:
        raise OutboundError(500, CODE_INTERNAL, "El mensaje reservado no existe")

    current = msg.current_status
    changed = False

    if result.outcome == OUTCOME_ACCEPTED:
        if next_current_status(current, STATUS_ACCEPTED) == STATUS_ACCEPTED:
            msg.current_status = STATUS_ACCEPTED
            msg.external_message_id = result.external_message_id
            msg.error_code = None
            msg.error_message_safe = None
            changed = True
    elif result.outcome == OUTCOME_AMBIGUOUS:
        if current in (STATUS_PENDING, STATUS_SENDING):
            msg.current_status = STATUS_UNKNOWN
            changed = True
    else:  # definitive_failure
        if next_current_status(current, STATUS_FAILED) == STATUS_FAILED:
            msg.current_status = STATUS_FAILED
            msg.error_code = result.error_code or None
            msg.error_message_safe = (
                safe_error(result.error_message_safe) if result.error_message_safe else None
            )
            # external_message_id solo si el sender lo provee explícitamente.
            if result.external_message_id:
                msg.external_message_id = result.external_message_id
            changed = True

    if changed:
        db.commit()
    else:
        db.rollback()
        logger.info(
            "[whatsapp-outbound] resultado tardío ignorado message_id=%s current=%s outcome=%s",
            message_id, current, result.outcome,
        )
    return msg


# --------------------------------------------------------------------------- #
# Traducción de estado interno → outcome de la respuesta
# --------------------------------------------------------------------------- #
def response_outcome(current_status: str) -> str:
    """Mapea el estado interno al `outcome` público (`accepted|failed|unknown`)."""
    if current_status in (STATUS_ACCEPTED, "sent", "delivered", "read"):
        return "accepted"
    if current_status == STATUS_FAILED:
        return "failed"
    return "unknown"  # pending | sending | unknown

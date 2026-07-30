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

from sqlalchemy import update
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
    VALID_OUTCOMES,
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
# Códigos internos de resultado del sender (1I.1b). NUNCA exponen detalle crudo de Meta.
CODE_SENDER_EXCEPTION = "WHATSAPP_SENDER_EXCEPTION"
CODE_ACCEPTED_NO_EXTERNAL_ID = "WHATSAPP_ACCEPTED_WITHOUT_EXTERNAL_ID"
CODE_INVALID_RESULT = "WHATSAPP_INVALID_SENDER_RESULT"

_MSG_AMBIGUOUS = "outbound result is ambiguous"
_MSG_ACCEPTED_NO_ID = "provider accepted response without message identifier"
_MSG_INVALID_RESULT = "invalid sender result"


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
def _valid_wa_id(value: Optional[str]) -> bool:
    """wa_id: dígitos, largo plausible (formato que genera el normalizer, sin `+`)."""
    return bool(value) and value.isdigit() and 8 <= len(value) <= 15


def _valid_phone_e164(value: Optional[str]) -> bool:
    """
    phone_e164: el normalizer persiste `+`+dígitos (`normalize_wa_id_to_e164` → `+549…`).
    Se acepta también el formato histórico de solo dígitos (`549…`) por robustez; el valor
    NO se modifica antes de pasarlo al sender (el cliente real de 1I.2 lo formatea).
    """
    if not value:
        return False
    digits = value[1:] if value.startswith("+") else value
    return digits.isdigit() and 8 <= len(digits) <= 15


def resolve_meta_recipient(db: Session, contact_id: int) -> Optional[str]:
    """
    Destinatario Meta del contacto, en orden ESTRICTO de preferencia:

        1) wa_id primario · 2) wa_id no-primario · 3) phone_e164 primario · 4) phone_e164

    Dentro de cada grupo se recorren TODOS los candidatos por `id` ascendente (orden
    determinista), se ignoran los inválidos y se devuelve el primer válido. Valida el
    formato básico SIN modificar el valor. NUNCA usa el display_number de la línea, el
    phone_masked, el nombre del contacto ni el teléfono del lead/vendedor.
    """
    I = models.WhatsAppContactIdentifier
    rows = (
        db.query(I.id, I.identifier_type, I.identifier_value, I.is_primary)
        .filter(
            I.contact_id == contact_id,
            I.provider == PROVIDER,
            I.identifier_type.in_([_WA_ID, _PHONE_E164]),
        )
        .order_by(I.id.asc())
        .all()
    )

    for itype, primary, validator in (
        (_WA_ID, True, _valid_wa_id),
        (_WA_ID, False, _valid_wa_id),
        (_PHONE_E164, True, _valid_phone_e164),
        (_PHONE_E164, False, _valid_phone_e164),
    ):
        for _id, t, value, is_primary in rows:  # ya ordenado por id asc
            if t == itype and bool(is_primary) == primary and validator(value):
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


def _cas_pending_to_sending(db: Session, message_id: int) -> bool:
    """
    Compare-and-set atómico `pending` → `sending` vía UPDATE condicional.

    Devuelve True SOLO si actualizó exactamente una fila (`WHERE current_status='pending'`).
    Si el mensaje ya avanzó (delivered/failed/etc.) el UPDATE no matchea y devuelve False:
    el llamador NO debe invocar al sender.
    """
    M = models.WhatsAppMessage
    res = db.execute(
        update(M)
        .where(M.id == message_id, M.current_status == STATUS_PENDING)
        .values(current_status=STATUS_SENDING)
    )
    db.commit()
    return res.rowcount == 1


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

    # 11) CAS OBLIGATORIO pending → sending. Solo se invoca al sender (Reserved) si el
    #     UPDATE condicional actualizó EXACTAMENTE una fila. Si no, NUNCA se envía.
    if not _cas_pending_to_sending(db, message_id):
        db.expire_all()
        current = db.query(M).filter(M.id == message_id).first()
        if current is None:
            # Estado inconsistente: la fila recién reservada desapareció.
            raise OutboundError(500, CODE_INTERNAL, "La reserva desapareció tras el CAS")
        # El mensaje ya no estaba `pending` (avanzó por otra vía): es la MISMA solicitud
        # (mismo client_request_id) ⇒ replay idempotente, sin reenviar.
        logger.info("[whatsapp-outbound] CAS pending->sending sin efecto message_id=%s current=%s",
                    message_id, current.current_status)
        return Replay(message=current)

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

    def to_unknown(code, message_safe):
        # `unknown` NUNCA degrada un estado ya avanzado (sent/delivered/read/failed).
        if current in (STATUS_PENDING, STATUS_SENDING):
            msg.current_status = STATUS_UNKNOWN
            msg.error_code = code
            msg.error_message_safe = message_safe
            return True
        return False

    if result.outcome not in VALID_OUTCOMES:
        # Un outcome desconocido NO entra como definitive_failure: se trata como ambiguo.
        changed = to_unknown(CODE_INVALID_RESULT, _MSG_INVALID_RESULT)
    elif result.outcome == OUTCOME_ACCEPTED:
        external_id = (result.external_message_id or "").strip()
        if not external_id:
            # `accepted` sin identificador (null/vacío/whitespace) NO se guarda accepted.
            changed = to_unknown(CODE_ACCEPTED_NO_EXTERNAL_ID, _MSG_ACCEPTED_NO_ID)
        elif next_current_status(current, STATUS_ACCEPTED) == STATUS_ACCEPTED:
            msg.current_status = STATUS_ACCEPTED
            msg.external_message_id = result.external_message_id
            msg.error_code = None
            msg.error_message_safe = None
            changed = True
    elif result.outcome == OUTCOME_AMBIGUOUS:
        changed = to_unknown(
            result.error_code or None,
            safe_error(result.error_message_safe) if result.error_message_safe else None,
        )
    else:  # definitive_failure (outcome válido garantizado por la guarda de arriba)
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
            "[whatsapp-outbound] resultado sin efecto message_id=%s current=%s outcome=%s",
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

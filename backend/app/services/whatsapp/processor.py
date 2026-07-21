"""
Procesamiento de los elementos soportados de un webhook ya persistido.

Responsabilidades (una función por paso, para poder testearlas por separado):

    _resolve_line          línea destinataria a partir de `metadata.phone_number_id`
    _resolve_contact       contacto global por identificadores estables (wa_id)
    _resolve_conversation  hilo (línea, contacto)
    _process_message       alta idempotente de mensajes entrantes de texto
    _process_status        historial de estados + estado actual del mensaje

Estrategia transaccional
------------------------
El evento crudo ya fue confirmado por `events.persist_event`. Acá **cada elemento se
procesa en su propia transacción**: al terminar bien se hace `commit`, y si falla se
hace `rollback` y se sigue con el siguiente. Así un elemento defectuoso no arrastra a
los demás ni deja registros a medias, sin depender de SAVEPOINTs (que se comportan
distinto en SQLite y en PostgreSQL).

Reglas de negocio que NO se violan en esta etapa:
  - un contacto desconocido NUNCA se convierte en lead (no se escribe `leads`);
  - una línea desconocida NUNCA se crea automáticamente;
  - no se asigna vendedor automáticamente (`assigned_user_id` queda en NULL);
  - no se toca la rotación de leads ni nada de NORA.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from .config import PROVIDER
from .normalizer import (
    REASON_UNSUPPORTED_MESSAGE_TYPE,
    NormalizedEvent,
    NormalizedMessage,
    NormalizedStatus,
    normalize_wa_id_to_e164,
)
from .redaction import mask_external_id, mask_identifier, safe_error, short_key

logger = logging.getLogger("uvicorn.error")

# --- Constantes de dominio (strings, no enums PostgreSQL: arquitectura §5) ---
DIRECTION_INBOUND = "inbound"
CONVERSATION_OPEN = "open"
ORIGIN_CLOUD_API = "cloud_api"
IDENTIFIER_WA_ID = "wa_id"
IDENTIFIER_PHONE = "phone_e164"

# Estado inicial de un mensaje ENTRANTE: ya nos fue entregado por la plataforma.
INBOUND_INITIAL_STATUS = "delivered"

# Precedencia de estados de un mensaje saliente. Un estado nunca retrocede:
# llegar `delivered` después de `read` no baja el estado actual.
STATUS_PRECEDENCE = {"pending": 0, "accepted": 1, "sent": 2, "delivered": 3, "read": 4}
TERMINAL_DELIVERY_STATES = frozenset({"delivered", "read"})
STATUS_FAILED = "failed"

# Ventana de atención al cliente de WhatsApp (24 h desde el último mensaje entrante).
CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)

# Motivos de descarte (se registran en logs y en el reporte; nunca datos personales).
REASON_UNKNOWN_LINE = "unknown_line"
REASON_INACTIVE_LINE = "inactive_line"
REASON_UNSUPPORTED_OBJECT = "unsupported_object"
REASON_INVALID_ENVELOPE = "invalid_envelope"
REASON_UNSUPPORTED_FIELD = "unsupported_field"
REASON_UNSUPPORTED_STATUS = "unsupported_status"
# `REASON_UNSUPPORTED_MESSAGE_TYPE` y los motivos por elemento vienen del normalizador.
REASON_UNKNOWN_MESSAGE = "unknown_external_message"
REASON_MISSING_SENDER = "missing_sender"


@dataclass
class ProcessingReport:
    """Resumen (sin datos personales) de lo que hizo el procesador con un evento."""
    messages_created: int = 0
    messages_duplicated: int = 0
    statuses_created: int = 0
    statuses_duplicated: int = 0
    unsupported_items: int = 0
    skipped_reasons: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def handled_items(self) -> int:
        return (self.messages_created + self.messages_duplicated
                + self.statuses_created + self.statuses_duplicated)

    def resolve_status(self) -> str:
        """Traduce el reporte al `processing_status` del evento."""
        if self.errors:
            return "failed"
        if self.handled_items > 0:
            return "processed"
        return "ignored"

    def summary_error(self) -> Optional[str]:
        """
        Texto para `last_error_safe`.

        Los errores van tal cual. Los motivos de DESCARTE se guardan con el prefijo
        explícito `skipped:` — sin él, un evento `processed` con elementos descartados
        (un `text` procesado y una `image` ignorada) no dejaría ninguna traza salvo el
        `raw_payload`, que se purga a los 30 días; y sin prefijo un evento exitoso
        parecería fallado. Un evento sin descartes ni errores deja la columna en NULL.
        """
        if self.errors:
            return safe_error("; ".join(self.errors))
        if self.skipped_reasons:
            motivos = ",".join(sorted(set(self.skipped_reasons)))
            return safe_error(f"skipped:{motivos}")
        return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _max_dt(current: Optional[datetime], candidate: Optional[datetime]) -> Optional[datetime]:
    """
    Máximo de dos timestamps tolerante a naive/aware.

    SQLite (tests) devuelve datetimes naive aunque la columna sea `timezone=True`;
    comparar naive con aware lanza TypeError. En ese caso se prefiere el valor nuevo.
    """
    if candidate is None:
        return current
    if current is None:
        return candidate
    try:
        return current if current >= candidate else candidate
    except TypeError:
        return candidate


def next_current_status(current: Optional[str], new: Optional[str]) -> Optional[str]:
    """
    Precedencia explícita de estados (§11 del plan):

        pending < sent < delivered < read     (`accepted` entre pending y sent)

    - `failed` se aplica salvo que ya exista prueba de entrega (`delivered`/`read`).
    - Desde `failed`, solo una confirmación real de entrega/lectura puede superarlo.
    - Estados fuera de orden nunca retroceden el estado actual.
    """
    if not new:
        return current
    if new == STATUS_FAILED:
        return current if current in TERMINAL_DELIVERY_STATES else STATUS_FAILED
    if current == STATUS_FAILED:
        return new if new in TERMINAL_DELIVERY_STATES else current
    if STATUS_PRECEDENCE.get(new, -1) > STATUS_PRECEDENCE.get(current, -1):
        return new
    return current


# --------------------------------------------------------------------------- #
# Resolución de línea / contacto / conversación
# --------------------------------------------------------------------------- #
def _resolve_line(db: Session, phone_number_id: Optional[str]) -> Optional[models.WhatsAppLine]:
    """Busca la línea por `phone_number_id`. NUNCA la crea automáticamente."""
    if not phone_number_id:
        return None
    return (
        db.query(models.WhatsAppLine)
        .filter(
            models.WhatsAppLine.provider == PROVIDER,
            models.WhatsAppLine.phone_number_id == str(phone_number_id),
        )
        .first()
    )


def _find_identifier(db: Session, identifier_type: str, value: str):
    return (
        db.query(models.WhatsAppContactIdentifier)
        .filter(
            models.WhatsAppContactIdentifier.provider == PROVIDER,
            models.WhatsAppContactIdentifier.identifier_type == identifier_type,
            models.WhatsAppContactIdentifier.identifier_value == value,
        )
        .first()
    )


def _has_primary_identifier(db: Session, contact_id: int) -> bool:
    """¿El contacto ya tiene un identificador primario para ESTE proveedor?"""
    return (
        db.query(models.WhatsAppContactIdentifier)
        .filter(
            models.WhatsAppContactIdentifier.contact_id == contact_id,
            models.WhatsAppContactIdentifier.provider == PROVIDER,
            models.WhatsAppContactIdentifier.is_primary.is_(True),
        )
        .first()
    ) is not None


def _resolve_contact(db: Session, wa_id: str, profile_name: Optional[str],
                     seen_at: Optional[datetime]) -> models.WhatsAppContact:
    """
    Resuelve (o crea) el contacto global a partir de sus identificadores.

    Orden de coincidencia: `wa_id` (estable, preferido) y, como respaldo, el teléfono
    E.164 derivado. Solo se crea un contacto nuevo cuando ninguna coincidencia segura
    existe, para no duplicar personas.

    REGLA DE NEGOCIO: acá NO se crea ni se vincula ningún lead. `lead_id` queda NULL;
    la conversión a lead es manual y de una etapa posterior.
    """
    seen_at = seen_at or _utcnow()
    phone_e164 = normalize_wa_id_to_e164(wa_id)

    wa_identifier = _find_identifier(db, IDENTIFIER_WA_ID, wa_id)
    contact = wa_identifier.contact if wa_identifier else None

    phone_identifier = None
    if phone_e164:
        phone_identifier = _find_identifier(db, IDENTIFIER_PHONE, phone_e164)
        if contact is None and phone_identifier is not None:
            contact = phone_identifier.contact
        elif (contact is not None and phone_identifier is not None
              and phone_identifier.contact_id != contact.id):
            # Identificadores repartidos entre dos contactos: se respeta el `wa_id`
            # (más estable) y NO se fusiona nada automáticamente. Queda registrado por
            # id interno para que una etapa posterior resuelva la unificación.
            logger.warning(
                "[whatsapp-webhook] identificadores en contactos distintos "
                "wa_id_contact_id=%s phone_contact_id=%s",
                contact.id, phone_identifier.contact_id,
            )

    if contact is None:
        contact = models.WhatsAppContact(
            display_name=profile_name,
            lead_id=None,  # explícito: un contacto desconocido NO se convierte en lead
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )
        db.add(contact)
        db.flush()
    else:
        if profile_name and not contact.display_name:
            contact.display_name = profile_name
        if contact.first_seen_at is None:
            contact.first_seen_at = seen_at
        contact.last_seen_at = _max_dt(contact.last_seen_at, seen_at)

    if wa_identifier is None:
        # El `wa_id` es el identificador preferido, pero no se marca primario si el
        # contacto ya tiene uno: dos primarios simultáneos serían ambiguos.
        db.add(models.WhatsAppContactIdentifier(
            contact_id=contact.id, provider=PROVIDER,
            identifier_type=IDENTIFIER_WA_ID, identifier_value=wa_id,
            is_primary=not _has_primary_identifier(db, contact.id),
        ))
    if phone_e164 and phone_identifier is None:
        db.add(models.WhatsAppContactIdentifier(
            contact_id=contact.id, provider=PROVIDER,
            identifier_type=IDENTIFIER_PHONE, identifier_value=phone_e164, is_primary=False,
        ))
    db.flush()
    return contact


def _resolve_conversation(db: Session, line: models.WhatsAppLine, contact: models.WhatsAppContact,
                          inbound_at: Optional[datetime]) -> models.WhatsAppConversation:
    """
    Devuelve el hilo (línea, contacto), creándolo si no existe.

    El modelo tiene `unique(line_id, contact_id)`: hay como máximo UN hilo por par, así
    que un mensaje entrante sobre un hilo cerrado lo **reabre** en lugar de crear otro.
    La misma persona escribiendo a otra línea produce un hilo distinto.

    No se asigna vendedor: `assigned_user_id` queda NULL y la conversación queda en la
    bandeja "sin asignar" (visible para administradores en una etapa posterior).
    """
    inbound_at = inbound_at or _utcnow()
    conversation = (
        db.query(models.WhatsAppConversation)
        .filter(
            models.WhatsAppConversation.line_id == line.id,
            models.WhatsAppConversation.contact_id == contact.id,
        )
        .first()
    )
    if conversation is None:
        conversation = models.WhatsAppConversation(
            line_id=line.id,
            contact_id=contact.id,
            lead_id=None,
            assigned_user_id=None,      # sin asignación automática en esta etapa
            assignment_source=None,
            status=CONVERSATION_OPEN,
            last_message_at=inbound_at,
            last_inbound_at=inbound_at,
            customer_service_window_expires_at=inbound_at + CUSTOMER_SERVICE_WINDOW,
        )
        db.add(conversation)
        db.flush()
        return conversation

    if conversation.status != CONVERSATION_OPEN:
        conversation.status = CONVERSATION_OPEN
    conversation.last_message_at = _max_dt(conversation.last_message_at, inbound_at)
    conversation.last_inbound_at = _max_dt(conversation.last_inbound_at, inbound_at)
    conversation.customer_service_window_expires_at = _max_dt(
        conversation.customer_service_window_expires_at, inbound_at + CUSTOMER_SERVICE_WINDOW
    )
    db.flush()
    return conversation


# --------------------------------------------------------------------------- #
# Elementos
# --------------------------------------------------------------------------- #
def _find_status_event(db: Session, event_key: str) -> Optional[models.WhatsAppMessageStatusEvent]:
    return (
        db.query(models.WhatsAppMessageStatusEvent)
        .filter(models.WhatsAppMessageStatusEvent.event_key == event_key)
        .first()
    )


def _find_message_by_external_id(db: Session, external_id: str) -> Optional[models.WhatsAppMessage]:
    return (
        db.query(models.WhatsAppMessage)
        .filter(
            models.WhatsAppMessage.provider == PROVIDER,
            models.WhatsAppMessage.external_message_id == external_id,
        )
        .first()
    )


def _process_message(db: Session, line: models.WhatsAppLine, item: NormalizedMessage,
                     report: ProcessingReport) -> None:
    """
    Alta idempotente de un mensaje entrante, con UN reintento ante conflicto de unicidad.

    El reintento no es cosmético: si dos entregas concurrentes traen mensajes distintos
    de un contacto NUEVO, ambas pasan el SELECT de `_resolve_contact` y la segunda choca
    contra `uq_whatsapp_contact_identifiers_value` al hacer flush. Sin reintento ese
    mensaje se perdería (evento en `failed` y, hasta que exista el reprocesador, sin
    recuperación). En el reintento las filas de la otra transacción ya son visibles y el
    mensaje se inserta reusando el contacto.
    """
    # `line.id` se guarda ANTES: tras el rollback la instancia queda expirada y leer el
    # atributo dispararía un SELECT extra (o `ObjectDeletedError` si la fila cambió),
    # enmascarando el IntegrityError original.
    line_id = line.id
    try:
        _process_message_once(db, line, item, report)
    except IntegrityError:
        db.rollback()
        logger.info("[whatsapp-webhook] conflicto de unicidad, reintento único line_id=%s",
                    line_id)
        _process_message_once(db, line, item, report)


def _process_message_once(db: Session, line: models.WhatsAppLine, item: NormalizedMessage,
                          report: ProcessingReport) -> None:
    """Un intento de alta del mensaje entrante (una transacción propia)."""
    if not item.supported:
        report.unsupported_items += 1
        report.skipped_reasons.append(item.unsupported_reason or REASON_UNSUPPORTED_MESSAGE_TYPE)
        logger.info("[whatsapp-webhook] elemento no soportado motivo=%s type=%s line_id=%s",
                    item.unsupported_reason, item.message_type, line.id)
        return
    if not item.wa_id:
        report.skipped_reasons.append(REASON_MISSING_SENDER)
        return

    if _find_message_by_external_id(db, item.external_id) is not None:
        report.messages_duplicated += 1
        # Todavía no hay id interno: se usa una huella del id externo, nunca el id.
        logger.info("[whatsapp-webhook] mensaje duplicado ext=%s line_id=%s",
                    mask_external_id(item.external_id), line.id)
        return

    contact = _resolve_contact(db, item.wa_id, item.profile_name, item.provider_timestamp)
    conversation = _resolve_conversation(db, line, contact, item.provider_timestamp)

    message = models.WhatsAppMessage(
        conversation_id=conversation.id,
        provider=PROVIDER,
        external_message_id=item.external_id,
        direction=DIRECTION_INBOUND,
        message_type=item.message_type,
        text_body=item.text_body,
        current_status=INBOUND_INITIAL_STATUS,
        context_external_message_id=item.context_external_id,
        sender_user_id=None,
        origin=ORIGIN_CLOUD_API,
        provider_timestamp=item.provider_timestamp,
    )
    db.add(message)
    # El IntegrityError (unique parcial de (provider, external_message_id) o unique de
    # identificadores) lo maneja el reintento de `_process_message`: allí la fila ya es
    # visible y este mismo camino la detecta como duplicada.
    db.commit()

    report.messages_created += 1
    # Correlación por IDs INTERNOS (§13): ni el wamid completo, ni el wa_id, ni el texto.
    logger.info(
        "[whatsapp-webhook] mensaje procesado line_id=%s conversation_id=%s contact_id=%s "
        "message_id=%s",
        line.id, conversation.id, contact.id, message.id,
    )


def _process_status(db: Session, line: models.WhatsAppLine, item: NormalizedStatus,
                    report: ProcessingReport) -> None:
    """Registra el estado de un mensaje saliente y actualiza su estado actual."""
    if not item.supported or not item.event_key:
        report.unsupported_items += 1
        report.skipped_reasons.append(REASON_UNSUPPORTED_STATUS)
        return

    message = _find_message_by_external_id(db, item.external_message_id)
    if message is None:
        # Estado de un mensaje que no conocemos (p. ej. enviado desde la app de
        # WhatsApp Business antes de integrar la línea). Se ignora sin romper.
        report.skipped_reasons.append(REASON_UNKNOWN_MESSAGE)
        logger.info("[whatsapp-webhook] estado sin mensaje conocido ext=%s line_id=%s",
                    mask_external_id(item.external_message_id), line.id)
        return

    if _find_status_event(db, item.event_key) is not None:
        report.statuses_duplicated += 1
        return

    db.add(models.WhatsAppMessageStatusEvent(
        message_id=message.id,
        event_key=item.event_key,
        status=item.status,
        provider_timestamp=item.provider_timestamp,
        # Payload SANITIZADO: sin teléfono completo ni contenido del mensaje.
        safe_payload={
            "status": item.status,
            "recipient": mask_identifier(item.recipient_id),
            "error_code": item.error_code,
            "error_title": item.error_title,
        },
    ))

    anterior = message.current_status
    nuevo = next_current_status(anterior, item.status)
    message.current_status = nuevo
    # Los campos de error acompañan al estado EFECTIVO: un `failed` fuera de orden que
    # no logra superar a `delivered`/`read` no ensucia el mensaje, y un `delivered`
    # posterior a un `failed` limpia el error que ya no aplica.
    if nuevo == STATUS_FAILED:
        # Solo se pisa la causa si el evento nuevo trae una: un segundo `failed` sin
        # bloque `errors[]` no puede borrar el motivo que ya estaba registrado.
        if item.error_code or item.error_title:
            message.error_code = item.error_code
            message.error_message_safe = safe_error(item.error_title) or None
    elif anterior == STATUS_FAILED and nuevo in TERMINAL_DELIVERY_STATES:
        message.error_code = None
        message.error_message_safe = None
    db.add(message)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Solo es duplicado si la fila realmente está: cualquier otro IntegrityError
        # (FK, not-null) no puede contarse como éxito, o el evento quedaría marcado
        # `processed` sin haber persistido el estado.
        if _find_status_event(db, item.event_key) is None:
            raise
        report.statuses_duplicated += 1
        return

    report.statuses_created += 1
    logger.info("[whatsapp-webhook] estado procesado status=%s message_id=%s line_id=%s",
                item.status, message.id, line.id)


# --------------------------------------------------------------------------- #
# Entrada del procesador
# --------------------------------------------------------------------------- #
def process_event(db: Session, normalized: NormalizedEvent) -> ProcessingReport:
    """
    Procesa los elementos soportados del evento ya persistido.

    Nunca lanza por un elemento individual: los errores se acumulan en el reporte
    (sanitizados) para que el router marque el evento como `failed` y quede para
    reproceso, respondiendo igualmente 200 a Meta (arquitectura §7).
    """
    report = ProcessingReport()

    if normalized.invalid_envelope:
        # No es "no aplicable": es un payload que no se pudo leer. Se reporta como error
        # para que el evento quede `failed` y el reprocesador lo revise, en vez de
        # `ignored`, que lo dejaría fuera de su radar con un diagnóstico falso.
        report.errors.append(REASON_INVALID_ENVELOPE)
        logger.warning("[whatsapp-webhook] envelope ilegible: no se pudo normalizar")
        return report

    if not normalized.supported_object:
        report.skipped_reasons.append(REASON_UNSUPPORTED_OBJECT)
        logger.info("[whatsapp-webhook] objeto no soportado object=%s",
                    short_key(normalized.object_type, 32))
        return report

    for change in normalized.changes:
        if not change.supported_field:
            report.skipped_reasons.append(REASON_UNSUPPORTED_FIELD)
            logger.info("[whatsapp-webhook] field no soportado field=%s",
                        short_key(change.field_name, 32))
            continue

        line = _resolve_line(db, change.phone_number_id)
        if line is None:
            # Línea desconocida: se conserva el webhook crudo para diagnóstico, pero
            # NO se crea una línea productiva automáticamente.
            report.skipped_reasons.append(REASON_UNKNOWN_LINE)
            logger.warning("[whatsapp-webhook] línea desconocida phone_number_id=%s",
                           mask_identifier(change.phone_number_id))
            continue
        if not line.is_active:
            # Trazabilidad sí (el evento queda almacenado), procesamiento comercial no.
            report.skipped_reasons.append(REASON_INACTIVE_LINE)
            logger.warning("[whatsapp-webhook] línea inactiva line_id=%s", line.id)
            continue

        # `logger.exception` NO se usa acá a propósito: el traceback de un error de
        # SQLAlchemy incluye la sentencia y los parámetros bindeados (texto del mensaje,
        # wa_id, nombre). Se logea solo el mensaje ya saneado por `safe_error`.
        for item in change.messages:
            try:
                _process_message(db, line, item, report)
            except Exception as exc:  # noqa: BLE001 — un ítem no puede tumbar el webhook
                db.rollback()
                report.errors.append(safe_error(exc))
                logger.error("[whatsapp-webhook] fallo procesando mensaje line_id=%s: %s",
                             line.id, safe_error(exc))

        for item in change.statuses:
            try:
                _process_status(db, line, item, report)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                report.errors.append(safe_error(exc))
                logger.error("[whatsapp-webhook] fallo procesando estado line_id=%s: %s",
                             line.id, safe_error(exc))

    return report

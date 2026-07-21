"""
Persistencia e idempotencia de los webhooks en `whatsapp_webhook_events`.

La tabla es la **fuente de verdad** de la recepción (arquitectura §7): primero se
persiste el evento y recién después se procesa. Si el procesamiento falla, el evento
queda con `processing_status='failed'` y `attempt_count` incrementado, disponible
para reproceso, en vez de perderse.

Estados de `processing_status` (arquitectura §5): pending | processing | processed |
failed | ignored.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from .config import PROVIDER, RAW_PAYLOAD_RETENTION_DAYS
from .redaction import safe_error, short_key

logger = logging.getLogger("uvicorn.error")

STATUS_PENDING = "pending"


@dataclass
class EventPersistResult:
    """Resultado de persistir un webhook: la fila y si ya existía (reintento de Meta)."""
    event: models.WhatsAppWebhookEvent
    duplicate: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def persist_event(db: Session, *, event_key: str, payload_hash: str,
                  event_type: Optional[str], raw_payload: Any) -> EventPersistResult:
    """
    Inserta el webhook crudo de forma idempotente y **confirma** la transacción.

    Doble protección de idempotencia:
      1. Lectura previa por (provider, event_key).
      2. Captura de `IntegrityError` del unique `uq_whatsapp_webhook_events_provider_event_key`
         (cubre la carrera entre dos réplicas procesando el mismo reintento a la vez).

    Cualquier otra excepción se propaga: el router la traduce a HTTP 500 y Meta
    reintentará (el evento NO quedó almacenado).
    """
    existing = (
        db.query(models.WhatsAppWebhookEvent)
        .filter(
            models.WhatsAppWebhookEvent.provider == PROVIDER,
            models.WhatsAppWebhookEvent.event_key == event_key,
        )
        .first()
    )
    if existing is not None:
        return EventPersistResult(event=existing, duplicate=True)

    event = models.WhatsAppWebhookEvent(
        provider=PROVIDER,
        event_key=event_key,
        payload_hash=payload_hash,
        event_type=event_type,
        processing_status=STATUS_PENDING,
        raw_payload=raw_payload,
        raw_payload_expires_at=_utcnow() + timedelta(days=RAW_PAYLOAD_RETENTION_DAYS),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otro proceso insertó el mismo event_key entre el SELECT y el INSERT.
        db.rollback()
        concurrent = (
            db.query(models.WhatsAppWebhookEvent)
            .filter(
                models.WhatsAppWebhookEvent.provider == PROVIDER,
                models.WhatsAppWebhookEvent.event_key == event_key,
            )
            .first()
        )
        if concurrent is None:
            raise
        logger.info("[whatsapp-webhook] evento duplicado por concurrencia event_key=%s",
                    short_key(event_key, 20))
        return EventPersistResult(event=concurrent, duplicate=True)

    db.refresh(event)
    return EventPersistResult(event=event, duplicate=False)


def mark_processing_result(db: Session, event: models.WhatsAppWebhookEvent, *,
                           status: str, error: Any = None) -> None:
    """
    Cierra el ciclo de procesamiento del evento: estado final, `processed_at`,
    `attempt_count` y error sanitizado. Nunca persiste el payload del error.
    """
    event.processing_status = status
    event.processed_at = _utcnow()
    event.attempt_count = (event.attempt_count or 0) + 1
    event.last_error_safe = safe_error(error) if error is not None else None
    db.add(event)
    db.commit()

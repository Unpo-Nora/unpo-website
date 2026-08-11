"""
Reconciliador de mensajes salientes (Etapa 1I.2B).

Cierra el ciclo de vida de los salientes que quedaron en estados no terminales por un
crash o un resultado ambiguo del provider:

  1. `sending` ATASCADO (más viejo que el umbral): el proceso murió entre el CAS
     `pending→sending` y la aplicación del resultado. Nunca vamos a saber qué pasó por
     esta vía -> se cierra como `unknown` (vía CAS, solo desde `sending`) con un
     error_code estable. Si Meta realmente lo envió, el webhook de statuses lo
     confirmará después (y la re-correlación de 1I.2B en el processor lo levanta).

  2. `unknown` VIEJO (más viejo que el umbral de revisión): no se puede resolver
     automáticamente sin adivinar. Se CUENTA y se LISTAN sus ids internos para revisión
     humana. No se muta nada.

REGLA CRÍTICA DEL CONTRATO (auditoría 1I.0 / §26 del plan): un `unknown` NUNCA se
re-envía automáticamente. Este módulo no importa el sender ni ningún cliente HTTP y
no realiza llamadas de red. Solo investiga, cierra estado o marca para revisión.
(Hay una guarda estática en los tests que verifica esas ausencias.)

Privacidad: en logs y salida solo ids internos, contadores y códigos estables. Nunca
texto, teléfonos, wa_id ni wamid.

Se ejecuta por CLI (cron/manual, proceso separado del web — arquitectura §9):

    python -m app.jobs.whatsapp_maintenance reconcile-outbound --limit 100
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ... import models
from .outbound import DIRECTION_OUTBOUND, STATUS_SENDING, STATUS_UNKNOWN
from .redaction import safe_error

logger = logging.getLogger("uvicorn.error")

# Código estable con el que se cierra un `sending` atascado (nunca detalle crudo).
CODE_RECONCILED_STALE_SENDING = "WHATSAPP_RECONCILED_STALE_SENDING"
MESSAGE_SAFE_STALE_SENDING = "reconciled: stale sending closed as unknown"

# Tope de ids listados en la salida del comando (el contador es siempre el total).
MAX_REVIEW_IDS_RENDERED = 50

SessionFactory = Callable[[], Session]
NowFn = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ReconcileResult:
    stale_sending_found: int = 0
    reconciled_to_unknown: int = 0
    cas_skipped: int = 0
    unknown_for_review: int = 0
    unknown_review_ids: List[int] = field(default_factory=list)
    operational_error: Optional[str] = None

    def render(self) -> str:
        # Solo enteros, ids internos y códigos estables: sin ningún dato del mensaje.
        ids = ",".join(str(i) for i in self.unknown_review_ids[:MAX_REVIEW_IDS_RENDERED])
        if len(self.unknown_review_ids) > MAX_REVIEW_IDS_RENDERED:
            ids += ",..."
        return "\n".join([
            "WHATSAPP_RECONCILE_RESULT",
            f"stale_sending_found={self.stale_sending_found}",
            f"reconciled_to_unknown={self.reconciled_to_unknown}",
            f"cas_skipped={self.cas_skipped}",
            f"unknown_for_review={self.unknown_for_review}",
            f"unknown_review_ids={ids or '-'}",
        ])


def close_stale_sending(db: Session, message_id: int) -> bool:
    """
    CAS `sending → unknown` de UN mensaje. Devuelve True si esta llamada lo cerró.

    El WHERE exige `current_status = 'sending'`: si entre la selección y este UPDATE
    el mensaje avanzó (el webhook aplicó un status real, u otra corrida lo cerró), el
    rowcount es 0 y NO se pisa nada. Nunca toca wamid, texto ni ningún otro campo.
    """
    result = db.execute(
        update(models.WhatsAppMessage)
        .where(
            models.WhatsAppMessage.id == message_id,
            models.WhatsAppMessage.direction == DIRECTION_OUTBOUND,
            models.WhatsAppMessage.current_status == STATUS_SENDING,
        )
        .values(
            current_status=STATUS_UNKNOWN,
            error_code=CODE_RECONCILED_STALE_SENDING,
            error_message_safe=MESSAGE_SAFE_STALE_SENDING,
        )
    )
    db.commit()
    return result.rowcount == 1


def reconcile_outbound(session_factory: SessionFactory, *, stale_sending_seconds: int,
                       unknown_review_seconds: int, batch_size: int,
                       now_fn: NowFn = _utcnow) -> ReconcileResult:
    """
    Una pasada del reconciliador, por lotes. Idempotente: una segunda corrida sin
    cambios en el medio no reconcilia nada nuevo. Jamás re-envía.
    """
    result = ReconcileResult()
    now = now_fn()
    M = models.WhatsAppMessage

    # ------- 1) sending atascados -> unknown (CAS por mensaje) -------------------
    sending_cutoff = now - timedelta(seconds=stale_sending_seconds)
    try:
        with session_factory() as db:
            stale_ids = db.execute(
                select(M.id)
                .where(
                    M.direction == DIRECTION_OUTBOUND,
                    M.current_status == STATUS_SENDING,
                    M.updated_at <= sending_cutoff,
                )
                .order_by(M.updated_at)
                .limit(batch_size)
            ).scalars().all()

            result.stale_sending_found = len(stale_ids)
            for message_id in stale_ids:
                if close_stale_sending(db, message_id):
                    result.reconciled_to_unknown += 1
                    logger.info(
                        "[whatsapp-reconcile] sending atascado cerrado como unknown "
                        "message_id=%s error_code=%s",
                        message_id, CODE_RECONCILED_STALE_SENDING,
                    )
                else:
                    # El mensaje avanzó entre la selección y el CAS: mejor noticia
                    # posible (un status real le ganó al reconciliador).
                    result.cas_skipped += 1
                    logger.info("[whatsapp-reconcile] CAS omitido (el mensaje avanzó) "
                                "message_id=%s", message_id)
    except SQLAlchemyError as exc:
        result.operational_error = safe_error(exc)
        logger.error("[whatsapp-reconcile] fallo operacional en sending atascados: %s",
                     safe_error(exc))
        return result

    # ------- 2) unknown viejos -> solo listar para revisión humana ---------------
    review_cutoff = now - timedelta(seconds=unknown_review_seconds)
    try:
        with session_factory() as db:
            review_ids = db.execute(
                select(M.id)
                .where(
                    M.direction == DIRECTION_OUTBOUND,
                    M.current_status == STATUS_UNKNOWN,
                    M.updated_at <= review_cutoff,
                )
                .order_by(M.updated_at)
                .limit(batch_size)
            ).scalars().all()

            result.unknown_for_review = len(review_ids)
            result.unknown_review_ids = list(review_ids)
            if review_ids:
                logger.info("[whatsapp-reconcile] unknown viejos para revisión count=%s",
                            len(review_ids))
    except SQLAlchemyError as exc:
        result.operational_error = safe_error(exc)
        logger.error("[whatsapp-reconcile] fallo operacional en unknown viejos: %s",
                     safe_error(exc))

    return result

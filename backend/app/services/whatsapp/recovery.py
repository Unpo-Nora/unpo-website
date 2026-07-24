"""
Reprocesamiento de eventos de webhook y purga de payloads (Etapa 1D).

Este servicio opera SOBRE la tabla `whatsapp_webhook_events`. No hay SQL en los
comandos ni en los routers: toda la lógica de reclamo/proceso/purga vive acá.

Modelo de reclamo (por qué necesita el lease de la migración b1e9d4c7f0a2)
--------------------------------------------------------------------------
El `processor.process_event` de 1C **commitea internamente** por cada elemento, así
que un `SELECT ... FOR UPDATE SKIP LOCKED` no puede mantener el row lock durante todo
el procesamiento. Para garantizar "cada evento se reclama una sola vez" bajo
concurrencia, el reclamo marca el evento como `processing` (estado NO elegible) en una
transacción corta y atómica, con `processing_started_at` = ahora. Si el worker cae
entre el reclamo y el cierre, el evento queda en `processing`; se recupera cuando su
lease vence (`processing_started_at < now - lease`), detectado sin ambigüedad gracias
a ese timestamp.

Estrategia transaccional
------------------------
1. Reclamo: `SELECT ... FOR UPDATE SKIP LOCKED` + `UPDATE ... processing` + commit.
   (En SQLite `SKIP LOCKED` se ignora; la concurrencia REAL se valida en PostgreSQL.)
2. Cada evento reclamado se procesa en su **propia** sesión/transacción, reutilizando
   `process_event` (misma lógica de contactos/identificadores/conversaciones/mensajes/
   estados; sin lógica paralela).
3. El resultado marca el evento (`processed`/`ignored`/`failed`) y libera el lease.

Privacidad: nada de payloads, teléfonos, nombres, wa_id/wamid, texto ni SQL en logs.
Solo id interno del evento, contadores, estado y motivos internos sanitizados.
"""

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from sqlalchemy import and_, case, func, null, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ... import models
from . import config
from .normalizer import normalize_envelope
from .processor import process_event
from .redaction import safe_error

logger = logging.getLogger("uvicorn.error")

# Estados de `processing_status` (arquitectura §5).
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_PROCESSED = "processed"
STATUS_IGNORED = "ignored"
STATUS_FAILED = "failed"

# Motivos internos sanitizados (nunca datos personales).
REASON_PAYLOAD_MISSING = "payload_missing"
REASON_MAX_ATTEMPTS = "max_attempts_exhausted"

SessionFactory = Callable[[], Session]
NowFn = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_worker_id() -> str:
    """
    Identificador corto y aleatorio por ejecución. NO contiene hostname, email, usuario
    del sistema ni nada sensible: solo sirve para trazar qué corrida reclamó un evento.
    """
    return f"wrk-{secrets.token_hex(4)}"


# --------------------------------------------------------------------------- #
# Resultados (salida sanitizada)
# --------------------------------------------------------------------------- #
@dataclass
class ReprocessResult:
    claimed: int = 0
    processed: int = 0
    ignored: int = 0
    failed: int = 0
    skipped: int = 0
    payload_missing: int = 0
    exhausted: int = 0
    lease_lost: int = 0
    operational_error: Optional[str] = None

    def render(self) -> str:
        # Solo enteros y estado: sin ningún dato del evento.
        return "\n".join([
            "WHATSAPP_REPROCESS_RESULT",
            f"claimed={self.claimed}",
            f"processed={self.processed}",
            f"ignored={self.ignored}",
            f"failed={self.failed}",
            f"skipped={self.skipped}",
            f"payload_missing={self.payload_missing}",
            f"exhausted={self.exhausted}",
            f"lease_lost={self.lease_lost}",
        ])


@dataclass
class PurgeResult:
    eligible: int = 0
    purged: int = 0
    remaining: int = 0
    operational_error: Optional[str] = None

    def render(self) -> str:
        return "\n".join([
            "WHATSAPP_PURGE_RESULT",
            f"eligible={self.eligible}",
            f"purged={self.purged}",
            f"remaining={self.remaining}",
        ])


# --------------------------------------------------------------------------- #
# Reclamo atómico
# --------------------------------------------------------------------------- #
def _eligibility(now: datetime, lease_seconds: int, max_attempts: int):
    """
    Condición de elegibilidad para el reclamo (WHERE), sobre `WhatsAppWebhookEvent`.

    - `failed`: bajo el máximo de intentos, con payload, y con el backoff cumplido
      (`next_retry_at` NULL o vencido). Un `failed` sin payload NO se reclama por acá:
      ya es terminal (su payload se purgó) y reclamarlo sería un bucle.
    - `pending`: bajo el máximo, con payload, y más viejo que el lease (gracia): así no
      se roba un webhook recién recibido que el receptor está por marcar.
    - `processing`: lease vencido (crash). SIN filtro de payload ni de intentos, para
      poder CERRAR un lease colgado aunque haya agotado intentos o perdido el payload.
    """
    E = models.WhatsAppWebhookEvent
    lease_cutoff = now - timedelta(seconds=lease_seconds)
    return or_(
        and_(
            E.processing_status == STATUS_FAILED,
            E.attempt_count < max_attempts,
            E.raw_payload.isnot(None),
            or_(E.next_retry_at.is_(None), E.next_retry_at <= now),
        ),
        and_(
            E.processing_status == STATUS_PENDING,
            E.attempt_count < max_attempts,
            E.raw_payload.isnot(None),
            E.received_at <= lease_cutoff,
        ),
        and_(
            E.processing_status == STATUS_PROCESSING,
            E.processing_started_at.isnot(None),
            E.processing_started_at <= lease_cutoff,
        ),
    )


def _claim_batch(db: Session, *, now: datetime, lease_seconds: int, batch_size: int,
                 max_attempts: int, worker_id: str) -> List[int]:
    """
    Reclama atómicamente hasta `batch_size` eventos elegibles y devuelve sus ids.

    `SELECT ... FOR UPDATE SKIP LOCKED` toma el lock de las filas candidatas (en la misma
    transacción), el `UPDATE` las marca `processing` con lease y worker, y el commit las
    libera ya reclamadas. Dos workers concurrentes nunca ven las mismas filas: el segundo
    las saltea (SKIP LOCKED). En SQLite el for-update se ignora (sin concurrencia real).
    """
    E = models.WhatsAppWebhookEvent
    ids = db.execute(
        select(E.id)
        .where(_eligibility(now, lease_seconds, max_attempts))
        # Prioriza lo que antes debió reintentarse; `processing` (retry NULL) ordena por
        # recepción.
        .order_by(func.coalesce(E.next_retry_at, E.received_at))
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).scalars().all()

    if not ids:
        db.commit()
        return []

    db.execute(
        update(E)
        .where(E.id.in_(ids))
        .values(
            processing_status=STATUS_PROCESSING,
            processing_started_at=now,
            locked_by=worker_id,
            # Incremento ACOTADO: nunca supera `max_attempts`. Un `processing` atascado
            # que ya llegó al máximo se reclama solo para CERRARLO, sin inflar el contador.
            attempt_count=case(
                (E.attempt_count < max_attempts, E.attempt_count + 1),
                else_=E.attempt_count,
            ),
        )
    )
    db.commit()
    return list(ids)


# --------------------------------------------------------------------------- #
# Cierre del evento con FENCING obligatorio
# --------------------------------------------------------------------------- #
# El cierre NO alcanza con verificar la propiedad al empezar: `process_event` commitea
# internamente, así que el lease puede vencer DURANTE el procesamiento y otro worker
# tomar el evento. Por eso la escritura final es un UPDATE condicional con fencing sobre
# (id, processing_status='processing', locked_by, processing_started_at). Si otro worker
# re-reclamó el evento, esos campos ya no coinciden: 0 filas → el worker tardío perdió el
# lease y NO puede sobrescribir el resultado del propietario vigente.
def _finalize(db: Session, event_id: int, *, worker_id: str, claim_started_at: datetime,
              values: dict) -> bool:
    E = models.WhatsAppWebhookEvent
    res = db.execute(
        update(E)
        .where(
            E.id == event_id,
            E.processing_status == STATUS_PROCESSING,
            E.locked_by == worker_id,
            E.processing_started_at == claim_started_at,
        )
        .values(**values)
    )
    db.commit()
    return res.rowcount == 1


def _success_values(now: datetime, status: str, error: Optional[str]) -> dict:
    return dict(processing_status=status, processed_at=now, processing_started_at=None,
                locked_by=None, next_retry_at=None, last_error_safe=error)


def _failure_values(now: datetime, error: Optional[str],
                    next_retry_at: Optional[datetime]) -> dict:
    return dict(processing_status=STATUS_FAILED, processed_at=now,
                processing_started_at=None, locked_by=None,
                next_retry_at=next_retry_at, last_error_safe=error)


def _process_one(db: Session, event_id: int, *, worker_id: str, claim_started_at: datetime,
                 now: datetime, max_attempts: int, result: ReprocessResult) -> None:
    """
    Procesa un único evento reclamado y lo cierra con fencing.

    `claim_started_at` es el `processing_started_at` que escribió ESTE reclamo: sirve de
    fencing token junto con `worker_id`. Si al cerrar el fencing no matchea (otro worker
    tomó el lease vencido), el cierre no aplica y se cuenta `lease_lost`.
    """
    E = models.WhatsAppWebhookEvent
    event = db.get(E, event_id)
    if event is None:
        result.skipped += 1
        return
    attempt = event.attempt_count
    payload = event.raw_payload

    def close(values, ok_counter):
        if _finalize(db, event_id, worker_id=worker_id, claim_started_at=claim_started_at,
                     values=values):
            ok_counter()
        else:
            result.lease_lost += 1
            logger.info("[whatsapp-recovery] lease perdido event_id=%s", event_id)

    # 1) Sin payload → terminal (no se procesa, no genera bucle: queda failed sin payload).
    if payload is None:
        def _pm():
            result.payload_missing += 1
            result.exhausted += 1
        close(_failure_values(now, REASON_PAYLOAD_MISSING, None), _pm)
        return

    # 2) Alcanzó el máximo → se cierra como exhausted SIN reprocesar (arquitectura de
    #    reintentos: la reclamación que lleva attempt_count a max no vuelve a procesar).
    if attempt >= max_attempts:
        close(_failure_values(now, REASON_MAX_ATTEMPTS, None),
              lambda: setattr(result, "exhausted", result.exhausted + 1))
        return

    # 3) Reproceso normal, reutilizando el procesador de 1C (idempotente). Aunque el
    #    lease se haya perdido, `process_event` no duplica nada; el fencing del cierre
    #    impide sobrescribir al propietario vigente.
    error: Optional[str]
    try:
        normalized = normalize_envelope(payload)
        report = process_event(db, normalized)
        status = report.resolve_status()
        error = report.summary_error()
    except Exception as exc:  # noqa: BLE001 — un evento no puede tumbar el lote
        db.rollback()
        status = STATUS_FAILED
        error = safe_error(exc)

    if status in (STATUS_PROCESSED, STATUS_IGNORED):
        def _ok():
            if status == STATUS_PROCESSED:
                result.processed += 1
            else:
                result.ignored += 1
        close(_success_values(now, status, error), _ok)
        return

    # Falló el reproceso (attempt < max acá): se reintenta con backoff.
    next_retry = now + timedelta(seconds=config.backoff_seconds(attempt))
    close(_failure_values(now, error, next_retry),
          lambda: setattr(result, "failed", result.failed + 1))


# --------------------------------------------------------------------------- #
# Entradas públicas
# --------------------------------------------------------------------------- #
def reprocess(session_factory: SessionFactory, *, lease_seconds: int, batch_size: int,
              max_attempts: int, worker_id: str, now_fn: NowFn = _utcnow) -> ReprocessResult:
    """
    Reclama un lote de eventos elegibles y los reprocesa uno por uno.

    Un evento que falla (poison pill) NO detiene el lote: se marca y se sigue. Un error
    OPERACIONAL (la base no responde en el reclamo) sí aborta y se refleja en
    `operational_error` para que el comando devuelva código != 0.
    """
    result = ReprocessResult()
    # `claim_now` es el `processing_started_at` que quedará en las filas reclamadas: es
    # parte del fencing token, así que se conserva para el cierre.
    claim_now = now_fn()

    # Reclamo (transacción corta y propia).
    try:
        with session_factory() as db:
            claimed_ids = _claim_batch(
                db, now=claim_now, lease_seconds=lease_seconds, batch_size=batch_size,
                max_attempts=max_attempts, worker_id=worker_id,
            )
    except SQLAlchemyError as exc:
        result.operational_error = safe_error(exc)
        logger.error("[whatsapp-recovery] fallo operacional en el reclamo: %s", safe_error(exc))
        return result

    result.claimed = len(claimed_ids)
    logger.info("[whatsapp-recovery] lote reclamado claimed=%s worker=%s", result.claimed, worker_id)

    # Procesamiento (una transacción por evento; un fallo individual no corta el lote).
    for event_id in claimed_ids:
        try:
            with session_factory() as db:
                _process_one(db, event_id, worker_id=worker_id, claim_started_at=claim_now,
                             now=now_fn(), max_attempts=max_attempts, result=result)
        except SQLAlchemyError as exc:
            # Fallo al persistir el resultado de ESTE evento: se cuenta como skipped y se
            # continúa. El lease vencerá y el evento se recuperará en otra corrida.
            result.skipped += 1
            logger.error("[whatsapp-recovery] fallo al cerrar event_id=%s: %s",
                         event_id, safe_error(exc))

    return result


def purge(session_factory: SessionFactory, *, batch_size: int,
          now_fn: NowFn = _utcnow) -> PurgeResult:
    """
    Anula `raw_payload` de los eventos cuya retención venció, por lotes.

    Elegible: `raw_payload IS NOT NULL AND raw_payload_expires_at <= now`. **No** purga
    eventos en `processing` aunque hayan vencido: podrían estar reprocesándose ahora
    mismo y necesitan su payload; su lease se resolverá antes. Idempotente: una segunda
    corrida no cambia nada. Nunca borra la fila; conserva todo el resto de columnas.
    """
    result = PurgeResult()
    now = now_fn()
    E = models.WhatsAppWebhookEvent

    eligible_where = and_(
        E.raw_payload.isnot(None),
        E.raw_payload_expires_at.isnot(None),
        E.raw_payload_expires_at <= now,
        E.processing_status != STATUS_PROCESSING,
    )

    try:
        with session_factory() as db:
            result.eligible = db.query(func.count(E.id)).filter(eligible_where).scalar() or 0

            # `FOR UPDATE SKIP LOCKED`: dos purgas concurrentes particionan las filas y
            # ninguna cuenta como purgada una fila que la otra ya tomó (igual que el
            # claim). En SQLite el for-update se ignora; los tests corren sin concurrencia.
            ids = db.execute(
                select(E.id).where(eligible_where)
                .order_by(E.raw_payload_expires_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            ).scalars().all()

            if ids:
                # `null()` fuerza SQL NULL: asignar Python `None` a una columna JSON/JSONB
                # guardaría el literal JSON 'null', que NO satisface `IS NOT NULL` y
                # dejaría la fila eternamente "elegible" para purgar.
                db.execute(update(E).where(E.id.in_(ids)).values(raw_payload=null()))
                db.commit()
                result.purged = len(ids)
            else:
                db.commit()

            result.remaining = db.query(func.count(E.id)).filter(eligible_where).scalar() or 0
    except SQLAlchemyError as exc:
        result.operational_error = safe_error(exc)
        logger.error("[whatsapp-recovery] fallo operacional en la purga: %s", safe_error(exc))
        return result

    logger.info("[whatsapp-recovery] purga eligible=%s purged=%s remaining=%s",
                result.eligible, result.purged, result.remaining)
    return result

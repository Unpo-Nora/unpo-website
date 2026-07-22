"""
Tests del reprocesador de eventos y la purga de payloads — Etapa 1D.

Aislado, sin base real: SQLite en memoria (StaticPool) con `PRAGMA foreign_keys=ON`,
esquema desde `Base.metadata` (Alembic sigue siendo el único gestor del PostgreSQL
productivo). `SKIP LOCKED` se ignora en SQLite; la concurrencia REAL se valida aparte
sobre PostgreSQL 17. `now` se inyecta para hacer determinísticos lease y backoff.

    python -m unittest tests.test_whatsapp_recovery -v
"""

import ast
import io
import logging
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests import whatsapp_fixtures as fx

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", fx.TEST_VERIFY_TOKEN)
os.environ.setdefault("WHATSAPP_META_APP_SECRET", fx.TEST_APP_SECRET)

from app import models  # noqa: E402
from app.database import Base  # noqa: E402
from app.services.whatsapp import config, recovery  # noqa: E402
from app.jobs import whatsapp_maintenance as cli  # noqa: E402

LOGGER_NAME = "uvicorn.error"

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION_FILE = os.path.join(
    BACKEND_DIR, "alembic", "versions",
    "b1e9d4c7f0a2_add_whatsapp_webhook_recovery_lease_fields.py",
)

# Instante fijo para todos los tests deterministas.
NOW = datetime(2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc)

# Distingue "sin argumento" (usar fixture default) de "payload NULL explícito".
_UNSET = object()


def _as_naive_utc(dt):
    """SQLite devuelve datetimes naive; se normaliza para comparar con instantes aware."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# =============================================================================== #
# Migración (estático) + backoff/config (unitario)
# =============================================================================== #
class RecoveryMigrationStaticTest(unittest.TestCase):
    def test_migration_exists_and_chains(self):
        src = _read(MIGRATION_FILE)
        self.assertIn("revision: str = 'b1e9d4c7f0a2'", src)
        self.assertIn("down_revision: Union[str, None] = 'efa066dfdf30'", src)

    def test_upgrade_adds_three_columns(self):
        src = _read(MIGRATION_FILE)
        up = src.split("def downgrade", 1)[0]
        for col in ("processing_started_at", "next_retry_at", "locked_by"):
            self.assertRegex(up, rf"add_column\(\s*TABLE,\s*sa\.Column\(\"{col}\"")

    def test_upgrade_creates_partial_indexes(self):
        up = _read(MIGRATION_FILE).split("def downgrade", 1)[0]
        self.assertIn("postgresql_where=sa.text(\"processing_status = 'processing'\")", up)
        self.assertIn("processing_status IN ('failed', 'pending')", up)

    def test_downgrade_drops_columns_and_indexes(self):
        down = "def downgrade" + _read(MIGRATION_FILE).split("def downgrade", 1)[1]
        for col in ("processing_started_at", "next_retry_at", "locked_by"):
            self.assertIn(f'drop_column(TABLE, "{col}")', down)
        self.assertIn("drop_index(IX_RETRY", down)
        self.assertIn("drop_index(IX_LEASE", down)

    def test_migration_is_additive_only(self):
        src = _read(MIGRATION_FILE)
        up = src.split("def downgrade", 1)[0]
        for forbidden in ("drop_table", "drop_column", "DELETE", "UPDATE ", "op.execute"):
            self.assertNotIn(forbidden, up, f"upgrade() no debe contener {forbidden}")
        self.assertNotIn("create_all", src)

    def test_migration_parses(self):
        ast.parse(_read(MIGRATION_FILE))


class BackoffConfigTest(unittest.TestCase):
    def test_backoff_schedule_is_deterministic(self):
        self.assertEqual(config.backoff_seconds(1), 60)
        self.assertEqual(config.backoff_seconds(2), 300)
        self.assertEqual(config.backoff_seconds(3), 900)
        self.assertEqual(config.backoff_seconds(4), 3600)
        self.assertEqual(config.backoff_seconds(5), 21600)

    def test_backoff_has_max_cap(self):
        for attempt in (5, 6, 10, 100):
            self.assertEqual(config.backoff_seconds(attempt), config.BACKOFF_MAX_SECONDS)

    def test_backoff_floor(self):
        self.assertEqual(config.backoff_seconds(0), 60)
        self.assertEqual(config.backoff_seconds(-3), 60)

    def test_env_reading_bounds(self):
        with mock.patch.dict(os.environ, {config.BATCH_SIZE_ENV: "999999"}):
            self.assertEqual(config.get_batch_size(), config.MAX_BATCH_SIZE)
        with mock.patch.dict(os.environ, {config.BATCH_SIZE_ENV: "0"}):
            self.assertEqual(config.get_batch_size(), config.MIN_BATCH_SIZE)
        with mock.patch.dict(os.environ, {config.BATCH_SIZE_ENV: "no-numero"}):
            self.assertEqual(config.get_batch_size(), config.DEFAULT_BATCH_SIZE)
        with mock.patch.dict(os.environ, {config.LEASE_SECONDS_ENV: "600"}):
            self.assertEqual(config.get_lease_seconds(), 600)
        with mock.patch.dict(os.environ, {config.MAX_ATTEMPTS_ENV: "0"}):
            self.assertEqual(config.get_max_attempts(), 1)  # piso: al menos 1

    def test_worker_id_has_no_sensitive_data(self):
        wid = recovery.generate_worker_id()
        self.assertTrue(wid.startswith("wrk-"))
        self.assertLessEqual(len(wid), 64)
        self.assertRegex(wid, r"^wrk-[0-9a-f]+$")


# =============================================================================== #
# Base común de integración (SQLite)
# =============================================================================== #
class RecoveryDBTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(cls.engine, "connect")
        def _fk(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    # --- helpers -----------------------------------------------------------
    def _session(self):
        return self.Session()

    def _seed_line(self, phone_number_id=fx.TEST_PHONE_NUMBER_ID, active=True):
        db = self._session()
        try:
            line = models.WhatsAppLine(
                provider="meta", phone_number_id=phone_number_id, waba_id=fx.TEST_WABA_ID,
                display_number=fx.TEST_DISPLAY_NUMBER, label="L", is_active=active,
            )
            db.add(line)
            db.commit()
            return line.id
        finally:
            db.close()

    def _seed_event(self, *, status="failed", payload=_UNSET, attempt_count=1,
                    next_retry_at=None, processing_started_at=None, received_at=None,
                    expires_at=None, event_key=None, locked_by=None):
        # payload=_UNSET → fixture default; payload=None → SQL NULL real; dict → tal cual.
        explicit_null = payload is None
        if payload is _UNSET:
            payload = fx.text_message_event()
        db = self._session()
        try:
            ev = models.WhatsAppWebhookEvent(
                provider="meta",
                event_key=event_key or f"sha256:{fx.TEST_MESSAGE_ID}:{status}:{attempt_count}",
                payload_hash="a" * 64,
                event_type="messages",
                processing_status=status,
                attempt_count=attempt_count,
                received_at=received_at or (NOW - timedelta(hours=1)),
                raw_payload=None if explicit_null else payload,
                raw_payload_expires_at=expires_at or (NOW + timedelta(days=30)),
                processing_started_at=processing_started_at,
                next_retry_at=next_retry_at,
                locked_by=locked_by,
            )
            db.add(ev)
            db.commit()
            eid = ev.id
            if explicit_null:
                # Forzar SQL NULL (asignar None a JSON guarda el literal 'null').
                from sqlalchemy import null as sql_null, update as sql_update
                db.execute(sql_update(models.WhatsAppWebhookEvent)
                           .where(models.WhatsAppWebhookEvent.id == eid)
                           .values(raw_payload=sql_null()))
                db.commit()
            return eid
        finally:
            db.close()

    def _get_event(self, event_id):
        db = self._session()
        try:
            return db.get(models.WhatsAppWebhookEvent, event_id)
        finally:
            db.close()

    def _count(self, model, **filters):
        db = self._session()
        try:
            q = db.query(model)
            for k, v in filters.items():
                q = q.filter(getattr(model, k) == v)
            return q.count()
        finally:
            db.close()

    def _reprocess(self, *, lease=config.DEFAULT_LEASE_SECONDS, batch=config.DEFAULT_BATCH_SIZE,
                   max_attempts=config.DEFAULT_MAX_ATTEMPTS, now=NOW, worker="wrk-test"):
        return recovery.reprocess(
            self.Session, lease_seconds=lease, batch_size=batch, max_attempts=max_attempts,
            worker_id=worker, now_fn=lambda: now,
        )

    def _purge(self, *, batch=config.DEFAULT_BATCH_SIZE, now=NOW):
        return recovery.purge(self.Session, batch_size=batch, now_fn=lambda: now)

    @staticmethod
    def _invalid_payload():
        # Envelope que no se puede normalizar → process_event lo marca failed.
        return {"object": "whatsapp_business_account",
                "entry": [{"id": "E", "changes": [
                    {"field": "messages", "value": {"contacts": {"no": "es lista"}}}]}]}


# =============================================================================== #
# Elegibilidad del reclamo
# =============================================================================== #
class ClaimEligibilityTest(RecoveryDBTest):
    def test_failed_event_is_claimed_and_processed(self):
        self._seed_line()
        eid = self._seed_event(status="failed", attempt_count=1, next_retry_at=None)
        r = self._reprocess()
        self.assertEqual((r.claimed, r.processed, r.failed), (1, 1, 0))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "processed")
        self.assertIsNone(ev.processing_started_at)
        self.assertIsNone(ev.next_retry_at)
        self.assertIsNone(ev.locked_by)
        self.assertIsNone(ev.last_error_safe)
        self.assertEqual(ev.attempt_count, 2)          # el claim incrementó
        self.assertIsNotNone(ev.processed_at)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)

    def test_pending_stale_is_claimed(self):
        self._seed_line()
        self._seed_event(status="pending", received_at=NOW - timedelta(seconds=1000))
        r = self._reprocess(lease=300)
        self.assertEqual((r.claimed, r.processed), (1, 1))

    def test_pending_recent_is_not_claimed(self):
        self._seed_line()
        self._seed_event(status="pending", received_at=NOW - timedelta(seconds=10))
        r = self._reprocess(lease=300)
        self.assertEqual(r.claimed, 0)   # gracia: un pending reciente no se roba

    def test_processing_stale_lease_is_recovered(self):
        self._seed_line()
        eid = self._seed_event(status="processing",
                               processing_started_at=NOW - timedelta(seconds=1000),
                               locked_by="wrk-crashed")
        r = self._reprocess(lease=300)
        self.assertEqual((r.claimed, r.processed), (1, 1))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "processed")
        self.assertNotEqual(ev.locked_by, "wrk-crashed")  # el lease se reemplaza... y limpia
        self.assertIsNone(ev.locked_by)

    def test_processing_active_lease_is_not_stolen(self):
        self._seed_line()
        eid = self._seed_event(status="processing",
                               processing_started_at=NOW - timedelta(seconds=60),
                               locked_by="wrk-otro")
        r = self._reprocess(lease=300)
        self.assertEqual(r.claimed, 0)
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "processing")
        self.assertEqual(ev.locked_by, "wrk-otro")   # intacto

    def test_next_retry_future_is_not_claimed(self):
        self._seed_line()
        self._seed_event(status="failed", next_retry_at=NOW + timedelta(hours=1))
        self.assertEqual(self._reprocess().claimed, 0)

    def test_next_retry_past_is_claimed(self):
        self._seed_line()
        self._seed_event(status="failed", next_retry_at=NOW - timedelta(minutes=1))
        self.assertEqual(self._reprocess().claimed, 1)

    def test_processed_and_ignored_are_not_eligible(self):
        self._seed_line()
        self._seed_event(status="processed")
        self._seed_event(status="ignored", event_key="sha256:otro")
        self.assertEqual(self._reprocess().claimed, 0)

    def test_batch_limit_is_respected(self):
        self._seed_line()
        for i in range(5):
            self._seed_event(status="failed", event_key=f"sha256:e{i}",
                             payload=fx.text_message_event(message_id=f"wamid.B{i}"))
        r = self._reprocess(batch=3)
        self.assertEqual(r.claimed, 3)
        # Quedan 2 elegibles para la próxima corrida.
        self.assertEqual(self._reprocess(batch=10).claimed, 2)

    def test_empty_batch(self):
        r = self._reprocess()
        self.assertEqual((r.claimed, r.processed, r.failed), (0, 0, 0))
        self.assertIsNone(r.operational_error)


# =============================================================================== #
# Reintentos, backoff, max attempts, payload missing, poison pill
# =============================================================================== #
class RetrySemanticsTest(RecoveryDBTest):
    def test_failed_reprocess_sets_backoff(self):
        eid = self._seed_event(status="failed", attempt_count=1, payload=self._invalid_payload())
        r = self._reprocess()
        self.assertEqual((r.claimed, r.failed, r.exhausted), (1, 1, 0))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "failed")
        self.assertEqual(ev.attempt_count, 2)
        self.assertEqual(_as_naive_utc(ev.next_retry_at),
                         _as_naive_utc(NOW + timedelta(seconds=config.backoff_seconds(2))))
        self.assertIsNone(ev.processing_started_at)
        self.assertIsNone(ev.locked_by)
        self.assertIn("invalid_envelope", ev.last_error_safe)

    def test_max_attempts_exhausted(self):
        eid = self._seed_event(status="failed", attempt_count=7, next_retry_at=None,
                               payload=self._invalid_payload())
        r = self._reprocess(max_attempts=8)
        self.assertEqual((r.claimed, r.exhausted, r.failed), (1, 1, 0))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "failed")
        self.assertEqual(ev.attempt_count, 8)
        self.assertIsNone(ev.next_retry_at)   # terminal, no se reintenta
        # Segunda corrida: exhausted no se vuelve a reclamar.
        self.assertEqual(self._reprocess(max_attempts=8).claimed, 0)

    def test_payload_missing_is_terminal_and_no_loop(self):
        # Un `processing` atascado sin payload: se cierra sin reprocesar, sin bucle.
        eid = self._seed_event(status="processing", payload=None,
                               processing_started_at=NOW - timedelta(seconds=1000))
        r = self._reprocess(lease=300)
        self.assertEqual((r.claimed, r.payload_missing, r.exhausted), (1, 1, 1))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "failed")
        self.assertIsNone(ev.next_retry_at)
        self.assertIsNone(ev.raw_payload)
        self.assertEqual(ev.last_error_safe, "payload_missing")
        # No genera bucle: un failed sin payload ya no es elegible.
        self.assertEqual(self._reprocess(lease=300).claimed, 0)

    def test_poison_pill_does_not_block_the_batch(self):
        self._seed_line()
        good = self._seed_event(status="failed", event_key="sha256:good",
                                payload=fx.text_message_event(message_id="wamid.GOOD"))
        bad = self._seed_event(status="failed", event_key="sha256:bad",
                               payload=self._invalid_payload())
        r = self._reprocess()
        self.assertEqual(r.claimed, 2)
        self.assertEqual(r.processed, 1)
        self.assertEqual(r.failed, 1)
        self.assertEqual(self._get_event(good).processing_status, "processed")
        self.assertEqual(self._get_event(bad).processing_status, "failed")
        self.assertEqual(self._count(models.WhatsAppMessage), 1)

    def test_unknown_line_reprocesses_as_ignored(self):
        # Sin línea sembrada: el evento se resuelve como ignored (no error), y cierra.
        eid = self._seed_event(status="failed")
        r = self._reprocess()
        self.assertEqual((r.claimed, r.ignored), (1, 1))
        ev = self._get_event(eid)
        self.assertEqual(ev.processing_status, "ignored")
        self.assertIsNotNone(ev.processed_at)
        self.assertIn("skipped:", ev.last_error_safe)   # motivo preservado
        self.assertIn("unknown_line", ev.last_error_safe)


# =============================================================================== #
# Idempotencia durante el reproceso
# =============================================================================== #
class ReprocessIdempotencyTest(RecoveryDBTest):
    def _reprocess_twice_same_event(self, payload):
        """Procesa un evento, lo fuerza a failed y lo reprocesa: no debe duplicar."""
        eid = self._seed_event(status="failed", payload=payload)
        self._reprocess()
        # Forzar re-elegibilidad manualmente.
        db = self._session()
        try:
            ev = db.get(models.WhatsAppWebhookEvent, eid)
            ev.processing_status = "failed"
            ev.next_retry_at = None
            ev.attempt_count = 1
            ev.processed_at = None
            db.commit()
        finally:
            db.close()
        return self._reprocess()

    def test_message_not_duplicated_on_reprocess(self):
        self._seed_line()
        r = self._reprocess_twice_same_event(fx.text_message_event())
        self.assertEqual(r.processed, 1)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)   # sin duplicar
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        self.assertEqual(self._count(models.WhatsAppConversation), 1)

    def test_status_not_duplicated_on_reprocess(self):
        line_id = self._seed_line()
        # Sembrar un mensaje saliente para que el estado tenga a quién aplicar.
        db = self._session()
        try:
            contact = models.WhatsAppContact()
            db.add(contact)
            db.flush()
            conv = models.WhatsAppConversation(line_id=line_id, contact_id=contact.id, status="open")
            db.add(conv)
            db.flush()
            db.add(models.WhatsAppMessage(
                conversation_id=conv.id, provider="meta",
                external_message_id=fx.TEST_OUTBOUND_MESSAGE_ID, direction="outbound",
                message_type="text", current_status="sent", origin="crm"))
            db.commit()
        finally:
            db.close()
        r = self._reprocess_twice_same_event(fx.status_event(status="delivered"))
        self.assertEqual(r.processed, 1)
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 1)

    def test_contacts_and_conversations_reused_across_events(self):
        self._seed_line()
        self._seed_event(status="failed", event_key="sha256:m1",
                         payload=fx.text_message_event(message_id="wamid.M1"))
        self._seed_event(status="failed", event_key="sha256:m2",
                         payload=fx.text_message_event(message_id="wamid.M2"))
        r = self._reprocess()
        self.assertEqual(r.processed, 2)
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        self.assertEqual(self._count(models.WhatsAppConversation), 1)
        self.assertEqual(self._count(models.WhatsAppMessage), 2)


# =============================================================================== #
# Claim exclusivo (secuencial, en SQLite) — la concurrencia real va en PostgreSQL
# =============================================================================== #
class ClaimExclusivityTest(RecoveryDBTest):
    def test_claimed_event_not_reclaimed_while_lease_valid(self):
        self._seed_line()
        eid = self._seed_event(status="failed")
        # Reclamo manual (sin procesar), dejando el evento en processing con lease fresco.
        db = self._session()
        try:
            ids = recovery._claim_batch(db, now=NOW, lease_seconds=300, batch_size=10,
                                        max_attempts=8, worker_id="wrk-a")
        finally:
            db.close()
        self.assertEqual(ids, [eid])
        # Un segundo reclamo con lease vigente no lo toma.
        db = self._session()
        try:
            ids2 = recovery._claim_batch(db, now=NOW, lease_seconds=300, batch_size=10,
                                         max_attempts=8, worker_id="wrk-b")
        finally:
            db.close()
        self.assertEqual(ids2, [])
        ev = self._get_event(eid)
        self.assertEqual(ev.locked_by, "wrk-a")
        self.assertEqual(ev.attempt_count, 2)   # un solo incremento


# =============================================================================== #
# Purga
# =============================================================================== #
class PurgeTest(RecoveryDBTest):
    def test_expired_payload_is_purged(self):
        eid = self._seed_event(status="failed", expires_at=NOW - timedelta(days=1))
        r = self._purge()
        self.assertEqual((r.eligible, r.purged, r.remaining), (1, 1, 0))
        ev = self._get_event(eid)
        self.assertIsNone(ev.raw_payload)
        # Preserva todo lo demás.
        self.assertEqual(ev.processing_status, "failed")
        self.assertIsNotNone(ev.event_key)
        self.assertIsNotNone(ev.payload_hash)
        self.assertIsNotNone(ev.received_at)
        self.assertEqual(ev.attempt_count, 1)

    def test_not_expired_payload_is_kept(self):
        eid = self._seed_event(status="failed", expires_at=NOW + timedelta(days=1))
        r = self._purge()
        self.assertEqual((r.eligible, r.purged), (0, 0))
        self.assertIsNotNone(self._get_event(eid).raw_payload)

    def test_exactly_now_is_purged(self):
        # expires_at == now → `<= now` incluye el borde.
        self._seed_event(status="failed", expires_at=NOW)
        self.assertEqual(self._purge().purged, 1)

    def test_already_null_payload_is_noop(self):
        self._seed_event(status="failed", payload=None, expires_at=NOW - timedelta(days=1))
        r = self._purge()
        self.assertEqual((r.eligible, r.purged), (0, 0))

    def test_processing_event_is_not_purged_even_if_expired(self):
        eid = self._seed_event(status="processing", expires_at=NOW - timedelta(days=1),
                               processing_started_at=NOW)
        r = self._purge()
        self.assertEqual((r.eligible, r.purged), (0, 0))
        self.assertIsNotNone(self._get_event(eid).raw_payload)   # protegido

    def test_multiple_batches(self):
        for i in range(5):
            self._seed_event(status="failed", event_key=f"sha256:p{i}",
                             expires_at=NOW - timedelta(days=1))
        first = self._purge(batch=3)
        self.assertEqual((first.eligible, first.purged, first.remaining), (5, 3, 2))
        second = self._purge(batch=3)
        self.assertEqual((second.eligible, second.purged, second.remaining), (2, 2, 0))

    def test_second_purge_is_idempotent(self):
        self._seed_event(status="failed", expires_at=NOW - timedelta(days=1))
        self._purge()
        r2 = self._purge()
        self.assertEqual((r2.eligible, r2.purged, r2.remaining), (0, 0, 0))

    def test_purge_empty(self):
        r = self._purge()
        self.assertEqual((r.eligible, r.purged, r.remaining), (0, 0, 0))
        self.assertIsNone(r.operational_error)


# =============================================================================== #
# Salida sanitizada y redacción de logs
# =============================================================================== #
class RedactionTest(RecoveryDBTest):
    SECRETO = "texto-ultra-confidencial-del-cliente"

    def _capture_logs(self, fn):
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(handler)
        nivel = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            fn()
        finally:
            logger.removeHandler(handler)
            logger.setLevel(nivel)
        return buffer.getvalue()

    def test_reprocess_logs_have_no_sensitive_data(self):
        self._seed_line()
        payload = fx.text_message_event(body=self.SECRETO, profile_name="Nombre Real Falso")
        self._seed_event(status="failed", payload=payload)
        logs = self._capture_logs(lambda: self._reprocess())
        for prohibido in (self.SECRETO, "Nombre Real Falso", fx.TEST_WA_ID,
                          fx.TEST_MESSAGE_ID, fx.TEST_APP_SECRET, fx.TEST_VERIFY_TOKEN):
            self.assertNotIn(prohibido, logs)

    def test_result_render_is_only_counters(self):
        r = recovery.ReprocessResult(claimed=3, processed=2, failed=1)
        texto = r.render()
        self.assertIn("WHATSAPP_REPROCESS_RESULT", texto)
        self.assertIn("claimed=3", texto)
        # Solo claves=enteros, nada más.
        for linea in texto.splitlines()[1:]:
            self.assertRegex(linea, r"^[a-z_]+=\d+$")

    def test_purge_render_is_only_counters(self):
        r = recovery.PurgeResult(eligible=5, purged=5, remaining=0)
        for linea in r.render().splitlines()[1:]:
            self.assertRegex(linea, r"^[a-z_]+=\d+$")


# =============================================================================== #
# Fallos operacionales y recuperación de sesión
# =============================================================================== #
class OperationalFailureTest(RecoveryDBTest):
    def test_claim_operational_error_is_reported(self):
        from sqlalchemy.exc import OperationalError
        with mock.patch.object(recovery, "_claim_batch",
                               side_effect=OperationalError("stmt", {}, Exception("db caída"))):
            r = self._reprocess()
        self.assertIsNotNone(r.operational_error)
        self.assertEqual(r.claimed, 0)

    def test_per_event_failure_does_not_abort_batch(self):
        self._seed_line()
        e1 = self._seed_event(status="failed", event_key="sha256:a",
                              payload=fx.text_message_event(message_id="wamid.A"))
        e2 = self._seed_event(status="failed", event_key="sha256:b",
                              payload=fx.text_message_event(message_id="wamid.B"))
        from sqlalchemy.exc import OperationalError
        real = recovery._process_one
        estado = {"n": 0}

        def _falla_el_primero(db, event_id, **kw):
            estado["n"] += 1
            if estado["n"] == 1:
                raise OperationalError("stmt", {}, Exception("fallo al cerrar"))
            return real(db, event_id, **kw)

        with mock.patch.object(recovery, "_process_one", side_effect=_falla_el_primero):
            r = self._reprocess()
        self.assertEqual(r.claimed, 2)
        self.assertEqual(r.skipped, 1)     # el que falló al cerrar
        self.assertEqual(r.processed, 1)   # el otro sí
        # Ambos fueron reclamados (processing); el que falló conserva su lease para
        # recuperarse en otra corrida.
        self.assertGreaterEqual(self._count(models.WhatsAppWebhookEvent,
                                            processing_status="processing"), 1)

    def test_session_reusable_after_integrity_error(self):
        # Dos eventos que materializan el MISMO mensaje: el segundo ve el duplicado.
        self._seed_line()
        self._seed_event(status="failed", event_key="sha256:d1",
                         payload=fx.text_message_event(message_id="wamid.DUP"))
        self._seed_event(status="failed", event_key="sha256:d2",
                         payload=fx.text_message_event(message_id="wamid.DUP", body="otro"))
        r = self._reprocess()
        self.assertEqual(r.claimed, 2)
        self.assertEqual(r.processed, 2)     # el 2º cuenta el duplicado como procesado
        self.assertEqual(self._count(models.WhatsAppMessage), 1)


# =============================================================================== #
# CLI
# =============================================================================== #
class CliTest(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = cli.main(argv)
        return code, buf.getvalue()

    def test_reprocess_exit_zero_and_output(self):
        stub = recovery.ReprocessResult(claimed=3, processed=3)
        with mock.patch.object(cli.recovery, "reprocess", return_value=stub) as m:
            code, out = self._run(["reprocess", "--limit", "10"])
        self.assertEqual(code, 0)
        self.assertIn("WHATSAPP_REPROCESS_RESULT", out)
        self.assertIn("claimed=3", out)
        # El limit validado se pasa como batch_size.
        self.assertEqual(m.call_args.kwargs["batch_size"], 10)

    def test_purge_exit_zero_and_output(self):
        stub = recovery.PurgeResult(eligible=2, purged=2, remaining=0)
        with mock.patch.object(cli.recovery, "purge", return_value=stub):
            code, out = self._run(["purge", "--limit", "50"])
        self.assertEqual(code, 0)
        self.assertIn("WHATSAPP_PURGE_RESULT", out)
        self.assertIn("purged=2", out)

    def test_operational_error_exit_nonzero(self):
        stub = recovery.ReprocessResult(operational_error="db down")
        with mock.patch.object(cli.recovery, "reprocess", return_value=stub):
            code, _ = self._run(["reprocess"])
        self.assertEqual(code, cli.EXIT_OPERATIONAL_ERROR)

    def test_individual_failures_still_exit_zero(self):
        # Eventos que fallaron individualmente NO son un fallo operacional del comando.
        stub = recovery.ReprocessResult(claimed=5, processed=3, failed=2)
        with mock.patch.object(cli.recovery, "reprocess", return_value=stub):
            code, _ = self._run(["reprocess"])
        self.assertEqual(code, 0)

    def test_invalid_limit_is_usage_error(self):
        for bad in ("0", "-1", "999999999", "abc"):
            code, _ = self._run(["reprocess", "--limit", bad])
            self.assertEqual(code, cli.EXIT_USAGE, f"--limit {bad} debería ser error de uso")

    def test_missing_subcommand_is_usage_error(self):
        code, _ = self._run([])
        self.assertEqual(code, cli.EXIT_USAGE)

    def test_unknown_subcommand_is_usage_error(self):
        code, _ = self._run(["frobnicate"])
        self.assertEqual(code, cli.EXIT_USAGE)

    def test_worker_id_is_sanitized(self):
        self.assertEqual(cli._sanitize_worker_id("host name/user@dom"), "hostnameuserdom")
        self.assertTrue(cli._sanitize_worker_id(None).startswith("wrk-"))
        self.assertLessEqual(len(cli._sanitize_worker_id("x" * 200)), 64)
        # No deja pasar caracteres peligrosos.
        self.assertNotIn("@", cli._sanitize_worker_id("a@b"))
        self.assertNotIn("/", cli._sanitize_worker_id("a/b"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

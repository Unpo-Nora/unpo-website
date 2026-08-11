"""
Tests de la Etapa 1I.2B: re-correlación status-antes-del-wamid + reconciliador.

Aislado, sin base real ni red: SQLite en memoria (StaticPool, FK ON), esquema desde
`Base.metadata`. Reusa el harness de `test_whatsapp_recovery.py` y los payloads
ficticios de `whatsapp_fixtures.py`.

Cubre:
  - `_process_status`: wamid desconocido + saliente en vuelo -> evento `failed`
    retryable; sin saliente en vuelo -> `ignored` (comportamiento 1C preservado);
  - e2e: el evento retryable se re-correlaciona vía `recovery.reprocess` cuando el
    wamid se persiste, sin duplicar statuses, con reintentos ACOTADOS;
  - reconciliador: sending atascado -> unknown vía CAS (código estable), unknown
    viejos solo se listan, nunca se muta lo que avanzó, batch respetado;
  - garantía estática: el reconciliador NO importa sender/httpx (jamás re-envía);
  - config y CLI.

    python -m unittest tests.test_whatsapp_reconcile -v
"""

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine, event
from sqlalchemy import update as sql_update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests import whatsapp_fixtures as fx

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", fx.TEST_VERIFY_TOKEN)
os.environ.setdefault("WHATSAPP_META_APP_SECRET", fx.TEST_APP_SECRET)

from app import models  # noqa: E402
from app.database import Base  # noqa: E402
from app.services.whatsapp import config, reconcile, recovery  # noqa: E402
from app.services.whatsapp.normalizer import normalize_envelope  # noqa: E402
from app.services.whatsapp.processor import (  # noqa: E402
    REASON_STATUS_BEFORE_WAMID,
    REASON_UNKNOWN_MESSAGE,
    process_event,
)
from app.jobs import whatsapp_maintenance as cli  # noqa: E402

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_RACE_WAMID = "wamid.TEST_RACE_001"


def _read_source(*relpath):
    with open(os.path.join(BACKEND_DIR, *relpath), "r", encoding="utf-8") as fh:
        return fh.read()


# =============================================================================== #
# Base común (SQLite en memoria)
# =============================================================================== #
class ReconcileDBTest(unittest.TestCase):
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

    def _seed_line(self, phone_number_id=fx.TEST_PHONE_NUMBER_ID, active=True,
                   display_number=fx.TEST_DISPLAY_NUMBER):
        db = self._session()
        try:
            line = models.WhatsAppLine(
                provider="meta", phone_number_id=phone_number_id, waba_id=fx.TEST_WABA_ID,
                display_number=display_number, label="L", is_active=active,
            )
            db.add(line)
            db.commit()
            return line.id
        finally:
            db.close()

    def _seed_conversation(self, line_id):
        db = self._session()
        try:
            contact = models.WhatsAppContact(
                display_name="Contacto Ficticio Test", lead_id=None,
                first_seen_at=NOW - timedelta(days=1),
                last_seen_at=NOW - timedelta(hours=2),
            )
            db.add(contact)
            db.flush()
            conv = models.WhatsAppConversation(
                line_id=line_id, contact_id=contact.id, lead_id=None,
                assigned_user_id=None, assignment_source=None, status="open",
                last_message_at=NOW - timedelta(hours=2),
                last_inbound_at=NOW - timedelta(hours=2),
                customer_service_window_expires_at=NOW + timedelta(hours=22),
            )
            db.add(conv)
            db.commit()
            return conv.id
        finally:
            db.close()

    def _seed_message(self, conversation_id, *, status="sending", wamid=None,
                      direction="outbound", updated_at=None, origin="crm"):
        db = self._session()
        try:
            msg = models.WhatsAppMessage(
                conversation_id=conversation_id, provider="meta",
                external_message_id=wamid,
                client_request_id=uuid.uuid4() if direction == "outbound" else None,
                direction=direction, message_type="text",
                text_body="texto ficticio de prueba",
                current_status=status, origin=origin,
            )
            db.add(msg)
            db.commit()
            mid = msg.id
            if updated_at is not None:
                # Explícito para simular antigüedad (gana sobre el onupdate).
                db.execute(sql_update(models.WhatsAppMessage)
                           .where(models.WhatsAppMessage.id == mid)
                           .values(updated_at=updated_at))
                db.commit()
            return mid
        finally:
            db.close()

    def _get_message(self, message_id):
        db = self._session()
        try:
            return db.get(models.WhatsAppMessage, message_id)
        finally:
            db.close()

    def _count_status_events(self):
        db = self._session()
        try:
            return db.query(models.WhatsAppMessageStatusEvent).count()
        finally:
            db.close()

    def _process(self, payload):
        db = self._session()
        try:
            return process_event(db, normalize_envelope(payload))
        finally:
            db.close()

    def _reconcile(self, *, stale=900, review=86_400, batch=100, now=NOW):
        return reconcile.reconcile_outbound(
            self.Session, stale_sending_seconds=stale, unknown_review_seconds=review,
            batch_size=batch, now_fn=lambda: now,
        )


# =============================================================================== #
# 1) Carrera status-antes-del-wamid en el processor
# =============================================================================== #
class StatusBeforeWamidTest(ReconcileDBTest):
    def test_inflight_marks_event_retryable(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="sending", wamid=None)

        report = self._process(fx.status_event(message_id=TEST_RACE_WAMID, status="sent"))

        self.assertIn(REASON_STATUS_BEFORE_WAMID, report.errors)
        self.assertEqual(report.resolve_status(), "failed")
        self.assertEqual(self._count_status_events(), 0)

    def test_inflight_unknown_also_marks_retryable(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="unknown", wamid=None)

        report = self._process(fx.status_event(message_id=TEST_RACE_WAMID, status="delivered"))
        self.assertIn(REASON_STATUS_BEFORE_WAMID, report.errors)
        self.assertEqual(report.resolve_status(), "failed")

    def test_without_inflight_keeps_ignored_behavior(self):
        self._seed_line()
        report = self._process(fx.status_event(message_id=fx.TEST_UNKNOWN_MESSAGE_ID))

        self.assertEqual(report.errors, [])
        self.assertIn(REASON_UNKNOWN_MESSAGE, report.skipped_reasons)
        self.assertEqual(report.resolve_status(), "ignored")

    def test_inflight_on_other_line_is_ignored(self):
        line_a = self._seed_line(fx.TEST_PHONE_NUMBER_ID)
        line_b = self._seed_line(fx.TEST_PHONE_NUMBER_ID_B,
                                 display_number=fx.TEST_DISPLAY_NUMBER_B)
        conv_b = self._seed_conversation(line_b)
        self._seed_message(conv_b, status="sending", wamid=None)

        report = self._process(fx.status_event(
            phone_number_id=fx.TEST_PHONE_NUMBER_ID, message_id=TEST_RACE_WAMID,
        ))
        self.assertEqual(report.errors, [])
        self.assertIn(REASON_UNKNOWN_MESSAGE, report.skipped_reasons)

    def test_inflight_requires_null_wamid(self):
        # Un saliente CON wamid distinto no es candidato (el suyo ya se persistió).
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="sending", wamid="wamid.TEST_OTRO_002")

        report = self._process(fx.status_event(message_id=TEST_RACE_WAMID))
        self.assertEqual(report.errors, [])
        self.assertIn(REASON_UNKNOWN_MESSAGE, report.skipped_reasons)

    def test_inbound_messages_do_not_count_as_inflight(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="delivered", wamid=None, direction="inbound",
                           origin="cloud_api")

        report = self._process(fx.status_event(message_id=TEST_RACE_WAMID))
        self.assertEqual(report.errors, [])
        self.assertIn(REASON_UNKNOWN_MESSAGE, report.skipped_reasons)


# =============================================================================== #
# 2) E2E: re-correlación vía recovery.reprocess
# =============================================================================== #
class RecorrelationE2ETest(ReconcileDBTest):
    def _seed_event(self, *, payload, status="failed", attempt_count=1, next_retry_at=None):
        db = self._session()
        try:
            ev = models.WhatsAppWebhookEvent(
                provider="meta",
                event_key=f"sha256:test-race-{attempt_count}",
                payload_hash="b" * 64,
                event_type="messages",
                processing_status=status,
                attempt_count=attempt_count,
                received_at=NOW - timedelta(hours=1),
                raw_payload=payload,
                raw_payload_expires_at=NOW + timedelta(days=30),
            )
            db.add(ev)
            db.commit()
            return ev.id
        finally:
            db.close()

    def _get_event(self, event_id):
        db = self._session()
        try:
            return db.get(models.WhatsAppWebhookEvent, event_id)
        finally:
            db.close()

    def _reprocess(self, *, now=NOW, worker="wrk-test"):
        return recovery.reprocess(
            self.Session, lease_seconds=config.DEFAULT_LEASE_SECONDS,
            batch_size=config.DEFAULT_BATCH_SIZE,
            max_attempts=config.DEFAULT_MAX_ATTEMPTS,
            worker_id=worker, now_fn=lambda: now,
        )

    def test_full_recorrelation_cycle(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        msg_id = self._seed_message(conv_id, status="sending", wamid=None)
        event_id = self._seed_event(
            payload=fx.status_event(message_id=TEST_RACE_WAMID, status="sent"),
        )

        # Corrida 1: el wamid todavía no está -> el evento sigue failed con backoff.
        result1 = self._reprocess()
        self.assertEqual(result1.claimed, 1)
        self.assertEqual(result1.failed, 1)
        ev = self._get_event(event_id)
        self.assertEqual(ev.processing_status, "failed")
        self.assertIn(REASON_STATUS_BEFORE_WAMID, ev.last_error_safe or "")
        self.assertIsNotNone(ev.next_retry_at)
        self.assertEqual(ev.attempt_count, 2)
        self.assertEqual(self._count_status_events(), 0)

        # El outbound completa la persistencia del wamid (apply_result del 1I.1).
        db = self._session()
        try:
            db.execute(sql_update(models.WhatsAppMessage)
                       .where(models.WhatsAppMessage.id == msg_id)
                       .values(external_message_id=TEST_RACE_WAMID,
                               current_status="accepted"))
            db.commit()
        finally:
            db.close()

        # Corrida 2 (pasado el backoff): correlaciona y aplica el status.
        result2 = self._reprocess(now=NOW + timedelta(seconds=600))
        self.assertEqual(result2.claimed, 1)
        self.assertEqual(result2.processed, 1)
        ev = self._get_event(event_id)
        self.assertEqual(ev.processing_status, "processed")
        message = self._get_message(msg_id)
        self.assertEqual(message.current_status, "sent")
        self.assertEqual(self._count_status_events(), 1)

        # Corrida 3: nada elegible; sin duplicados.
        result3 = self._reprocess(now=NOW + timedelta(seconds=1200))
        self.assertEqual(result3.claimed, 0)
        self.assertEqual(self._count_status_events(), 1)

    def test_retry_cycle_is_bounded(self):
        # A un intento del máximo: el reclamo lleva attempt_count al tope y el cierre
        # es `exhausted` SIN reprocesar. La carrera JAMÁS produce un bucle infinito.
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="sending", wamid=None)
        event_id = self._seed_event(
            payload=fx.status_event(message_id=TEST_RACE_WAMID),
            attempt_count=config.DEFAULT_MAX_ATTEMPTS - 1,
        )

        result = self._reprocess()
        self.assertEqual(result.exhausted, 1)
        ev = self._get_event(event_id)
        self.assertEqual(ev.processing_status, "failed")
        self.assertIn("max_attempts", ev.last_error_safe or "")


# =============================================================================== #
# 3) Reconciliador
# =============================================================================== #
class ReconcileOutboundTest(ReconcileDBTest):
    def test_stale_sending_closed_as_unknown(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        stale_id = self._seed_message(conv_id, status="sending",
                                      updated_at=NOW - timedelta(hours=1))

        result = self._reconcile(stale=900)
        self.assertEqual(result.stale_sending_found, 1)
        self.assertEqual(result.reconciled_to_unknown, 1)
        self.assertEqual(result.cas_skipped, 0)

        msg = self._get_message(stale_id)
        self.assertEqual(msg.current_status, "unknown")
        self.assertEqual(msg.error_code, reconcile.CODE_RECONCILED_STALE_SENDING)
        self.assertEqual(msg.error_message_safe, reconcile.MESSAGE_SAFE_STALE_SENDING)
        self.assertIsNone(msg.external_message_id)

    def test_fresh_sending_untouched(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        fresh_id = self._seed_message(conv_id, status="sending",
                                      updated_at=NOW - timedelta(seconds=60))

        result = self._reconcile(stale=900)
        self.assertEqual(result.stale_sending_found, 0)
        self.assertEqual(self._get_message(fresh_id).current_status, "sending")

    def test_terminal_and_accepted_states_untouched(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        old = NOW - timedelta(days=2)
        ids = {
            "accepted": self._seed_message(conv_id, status="accepted",
                                           wamid="wamid.TEST_A", updated_at=old),
            "delivered": self._seed_message(conv_id, status="delivered",
                                            wamid="wamid.TEST_B", updated_at=old),
            "failed": self._seed_message(conv_id, status="failed", updated_at=old),
            "pending": self._seed_message(conv_id, status="pending", updated_at=old),
        }
        result = self._reconcile(stale=900)
        self.assertEqual(result.stale_sending_found, 0)
        for status, mid in ids.items():
            self.assertEqual(self._get_message(mid).current_status, status)

    def test_inbound_never_touched(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        # Un inbound jamás debería estar en `sending`, pero si un dato corrupto lo
        # pusiera ahí, el filtro de dirección lo protege igual.
        weird_id = self._seed_message(conv_id, status="sending", direction="inbound",
                                      origin="cloud_api", updated_at=NOW - timedelta(days=1))
        result = self._reconcile(stale=900)
        self.assertEqual(result.stale_sending_found, 0)
        self.assertEqual(self._get_message(weird_id).current_status, "sending")

    def test_cas_skips_message_that_advanced(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        accepted_id = self._seed_message(conv_id, status="accepted", wamid="wamid.TEST_C")

        db = self._session()
        try:
            self.assertFalse(reconcile.close_stale_sending(db, accepted_id))
        finally:
            db.close()
        self.assertEqual(self._get_message(accepted_id).current_status, "accepted")

    def test_unknown_old_listed_not_mutated(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        old_id = self._seed_message(conv_id, status="unknown",
                                    updated_at=NOW - timedelta(days=2))
        recent_id = self._seed_message(conv_id, status="unknown",
                                       updated_at=NOW - timedelta(hours=1))

        result = self._reconcile(review=86_400)
        self.assertEqual(result.unknown_for_review, 1)
        self.assertEqual(result.unknown_review_ids, [old_id])
        # Solo lectura: nada cambió en el mensaje.
        msg = self._get_message(old_id)
        self.assertEqual(msg.current_status, "unknown")
        self.assertIsNone(msg.error_code)
        self.assertEqual(self._get_message(recent_id).current_status, "unknown")

    def test_batch_limit_respected(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        for _ in range(3):
            self._seed_message(conv_id, status="sending",
                               updated_at=NOW - timedelta(hours=2))
        result = self._reconcile(stale=900, batch=2)
        self.assertEqual(result.stale_sending_found, 2)
        self.assertEqual(result.reconciled_to_unknown, 2)

    def test_second_run_is_idempotent(self):
        line_id = self._seed_line()
        conv_id = self._seed_conversation(line_id)
        self._seed_message(conv_id, status="sending", updated_at=NOW - timedelta(hours=1))

        first = self._reconcile(stale=900)
        self.assertEqual(first.reconciled_to_unknown, 1)
        second = self._reconcile(stale=900)
        self.assertEqual(second.stale_sending_found, 0)
        self.assertEqual(second.reconciled_to_unknown, 0)

    def test_render_output_is_sanitized_counters_only(self):
        result = reconcile.ReconcileResult(
            stale_sending_found=2, reconciled_to_unknown=1, cas_skipped=1,
            unknown_for_review=3, unknown_review_ids=[7, 8, 9],
        )
        out = result.render()
        self.assertIn("WHATSAPP_RECONCILE_RESULT", out)
        self.assertIn("reconciled_to_unknown=1", out)
        self.assertIn("unknown_review_ids=7,8,9", out)

    def test_render_caps_review_ids(self):
        result = reconcile.ReconcileResult(
            unknown_for_review=60,
            unknown_review_ids=list(range(1, 61)),
        )
        out = result.render()
        self.assertIn("...", out)
        self.assertNotIn("51", out.split("unknown_review_ids=")[1])


# =============================================================================== #
# 4) Garantías estáticas: el reconciliador JAMÁS puede re-enviar
# =============================================================================== #
class NoResendStaticGuaranteeTest(unittest.TestCase):
    def test_reconcile_module_has_no_sender_or_network(self):
        src = _read_source("app", "services", "whatsapp", "reconcile.py")
        for forbidden in ("httpx", "meta_sender", "send_text", "MetaGraphWhatsAppSender",
                          "DisabledWhatsAppSender", "graph.facebook.com"):
            self.assertNotIn(forbidden, src,
                             f"reconcile.py no debe contener '{forbidden}': jamás re-envía")

    def test_processor_does_not_import_outbound(self):
        # Guarda del ciclo: outbound importa de processor; nunca al revés.
        src = _read_source("app", "services", "whatsapp", "processor.py")
        self.assertNotIn("from .outbound", src)
        self.assertNotIn("import outbound", src)


# =============================================================================== #
# 5) Config y CLI
# =============================================================================== #
class ReconcileConfigTest(unittest.TestCase):
    def test_defaults(self):
        with mock.patch.dict(os.environ, {config.STALE_SENDING_SECONDS_ENV: "",
                                          config.UNKNOWN_REVIEW_SECONDS_ENV: ""}):
            self.assertEqual(config.get_stale_sending_seconds(),
                             config.DEFAULT_STALE_SENDING_SECONDS)
            self.assertEqual(config.get_unknown_review_seconds(),
                             config.DEFAULT_UNKNOWN_REVIEW_SECONDS)

    def test_bounds(self):
        with mock.patch.dict(os.environ, {config.STALE_SENDING_SECONDS_ENV: "1"}):
            self.assertEqual(config.get_stale_sending_seconds(), config.MIN_RECONCILE_SECONDS)
        with mock.patch.dict(os.environ, {config.UNKNOWN_REVIEW_SECONDS_ENV: "99999999999"}):
            self.assertEqual(config.get_unknown_review_seconds(), config.MAX_RECONCILE_SECONDS)
        with mock.patch.dict(os.environ, {config.STALE_SENDING_SECONDS_ENV: "no-numero"}):
            self.assertEqual(config.get_stale_sending_seconds(),
                             config.DEFAULT_STALE_SENDING_SECONDS)


class ReconcileCliTest(unittest.TestCase):
    def _fake_result(self, operational_error=None):
        return reconcile.ReconcileResult(operational_error=operational_error)

    def test_cli_runs_reconcile_with_defaults(self):
        with mock.patch.object(cli.reconcile, "reconcile_outbound",
                               return_value=self._fake_result()) as spy:
            code = cli.main(["reconcile-outbound"])
        self.assertEqual(code, cli.EXIT_OK)
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs["stale_sending_seconds"], config.get_stale_sending_seconds())
        self.assertEqual(kwargs["unknown_review_seconds"], config.get_unknown_review_seconds())

    def test_cli_accepts_explicit_thresholds(self):
        with mock.patch.object(cli.reconcile, "reconcile_outbound",
                               return_value=self._fake_result()) as spy:
            code = cli.main(["reconcile-outbound", "--limit", "10",
                             "--stale-sending-seconds", "600",
                             "--unknown-review-seconds", "3600"])
        self.assertEqual(code, cli.EXIT_OK)
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs["batch_size"], 10)
        self.assertEqual(kwargs["stale_sending_seconds"], 600)
        self.assertEqual(kwargs["unknown_review_seconds"], 3600)

    def test_cli_operational_error_exit_code(self):
        with mock.patch.object(cli.reconcile, "reconcile_outbound",
                               return_value=self._fake_result("db down")):
            code = cli.main(["reconcile-outbound"])
        self.assertEqual(code, cli.EXIT_OPERATIONAL_ERROR)

    def test_cli_rejects_out_of_range_threshold(self):
        code = cli.main(["reconcile-outbound", "--stale-sending-seconds", "1"])
        self.assertEqual(code, cli.EXIT_USAGE)


if __name__ == "__main__":
    unittest.main(verbosity=2)

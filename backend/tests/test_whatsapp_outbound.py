"""
Tests del núcleo de envío saliente de WhatsApp (Etapa 1I.1).

Convenciones de la suite: `unittest` (stdlib), SQLite en memoria (StaticPool) con
`PRAGMA foreign_keys=ON`, esquema desde `Base.metadata`, FastAPI mínima con
`routers/whatsapp_inbox`, y overrides de `get_db`, `get_current_user` y del sender.

NUNCA se llama a Meta: se inyecta un `FakeWhatsAppSender` que registra los comandos y
devuelve un `SendResult` configurable. Los tests de CONCURRENCIA real (FOR UPDATE) viven
en `PgConcurrencyTests`, que solo corre si se provee `WHATSAPP_OUTBOUND_PG_DSN`
(PostgreSQL 17 efímero).

    python -m unittest tests.test_whatsapp_outbound -v
"""

import asyncio
import os
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, models
from app.database import Base
from app.routers import whatsapp_inbox
from app.routers.auth import get_current_user
from app.services.whatsapp import outbound as ob
from app.services.whatsapp.sender import (
    OUTCOME_ACCEPTED,
    OUTCOME_AMBIGUOUS,
    OUTCOME_DEFINITIVE_FAILURE,
    SendResult,
)

WA_ENV = "WHATSAPP_OUTBOUND_ENABLED"

# Datos ficticios (nunca números reales de UNPO/NORA).
WA_ID_PRIMARY = "5491100000001"
WA_ID_SECONDARY = "5491100000002"
PHONE_E164 = "+5491100000003"
FAKE_WAMID = "wamid.TEST_FAKE_0001"

# Sentinela: distingue "el test no especificó destinatario" (generar uno único y válido)
# de "el test pidió explícitamente None" (sin identificadores → sin destinatario).
_UNSET = object()


class FakeWhatsAppSender:
    """Sender de test: NO hace red. Registra comandos y devuelve un resultado configurable
    (o levanta una excepción para simular una caída/desconexión = resultado ambiguo)."""

    def __init__(self, result=None, raises=None, delay=None):
        self.result = result if result is not None else SendResult(
            outcome=OUTCOME_ACCEPTED, external_message_id=FAKE_WAMID)
        self.raises = raises
        self.delay = delay  # segundos: mantiene el mensaje en `sending` (test concurrente)
        self.calls = []

    async def send_text(self, command):
        self.calls.append(command)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises is not None:
            raise self.raises
        return self.result


class _ASGIClient:
    def __init__(self, app):
        self._app = app

    def _request(self, method, url, **kwargs):
        async def _do():
            transport = ASGITransport(app=self._app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                return await ac.request(method, url, **kwargs)
        return asyncio.run(_do())

    def post(self, url, **kw):
        return self._request("POST", url, **kw)


class OutboundTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def _fk_on(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self._counter = 0
        self._seed()

        os.environ[WA_ENV] = "true"  # habilitado por defecto; el test de flag lo apaga
        self.sender = FakeWhatsAppSender()

        self.app = FastAPI()
        self.app.include_router(whatsapp_inbox.router)
        self.app.dependency_overrides[database.get_db] = self._get_db
        self.app.dependency_overrides[whatsapp_inbox.get_whatsapp_sender] = lambda: self.sender
        self.client = _ASGIClient(self.app)

    def tearDown(self):
        os.environ.pop(WA_ENV, None)
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _get_db(self):
        yield self.db

    def as_user(self, user):
        self.app.dependency_overrides[get_current_user] = lambda: user

    # --- seed -----------------------------------------------------------------
    def _seed(self):
        db = self.db
        self.line = models.WhatsAppLine(
            provider="meta", phone_number_id="PNID_ACTIVE", waba_id="WABA1",
            display_number="+540000000001", label="Linea Activa", is_active=True)
        self.line_inactive = models.WhatsAppLine(
            provider="meta", phone_number_id="PNID_INACTIVE", waba_id="WABA2",
            display_number="+540000000002", label="Linea Inactiva", is_active=False)
        db.add_all([self.line, self.line_inactive])
        db.commit()

        self.admin = models.User(email="admin@test.local", hashed_password="x",
                                 full_name="Admin", role="admin")
        self.seller = models.User(email="seller@test.local", hashed_password="x",
                                  full_name="Vendedor Send", role="vendedor")
        self.seller_view = models.User(email="view@test.local", hashed_password="x",
                                       full_name="Vendedor View", role="vendedor")
        self.seller_none = models.User(email="none@test.local", hashed_password="x",
                                       full_name="Vendedor Sin Acceso", role="vendedor")
        db.add_all([self.admin, self.seller, self.seller_view, self.seller_none])
        db.commit()

        db.add_all([
            # seller: can_view + can_send en la línea activa.
            models.WhatsAppLineUserAccess(line_id=self.line.id, user_id=self.seller.id,
                                          can_view=True, can_send=True),
            # seller_view: can_view pero can_send=False.
            models.WhatsAppLineUserAccess(line_id=self.line.id, user_id=self.seller_view.id,
                                          can_view=True, can_send=False),
        ])
        db.commit()

    def _make_conv(self, *, line=None, window="open",
                   wa_id_primary=_UNSET, wa_id=None, phone_primary=None, phone=None,
                   assigned=None):
        """Crea contacto + identificadores + conversación con la ventana indicada.

        Si el test no especifica destinatario, se genera un `wa_id` primario ÚNICO y
        válido (los identificadores son únicos globalmente). Un `wa_id_primary=None`
        explícito significa "sin destinatario"."""
        line = line or self.line
        if wa_id_primary is _UNSET:
            self._counter += 1
            wa_id_primary = f"549110000{self._counter:04d}"
        db = self.db
        contact = models.WhatsAppContact(display_name="Contacto Test")
        db.add(contact)
        db.flush()
        idents = []
        if wa_id_primary:
            idents.append(("wa_id", wa_id_primary, True))
        if wa_id:
            idents.append(("wa_id", wa_id, False))
        if phone_primary:
            idents.append(("phone_e164", phone_primary, True))
        if phone:
            idents.append(("phone_e164", phone, False))
        for itype, value, primary in idents:
            db.add(models.WhatsAppContactIdentifier(
                contact_id=contact.id, provider="meta", identifier_type=itype,
                identifier_value=value, is_primary=primary))

        now = datetime.now(timezone.utc)
        expires = {"open": now + timedelta(hours=12),
                   "closed": now - timedelta(hours=1),
                   "null": None}[window]
        conv = models.WhatsAppConversation(
            line_id=line.id, contact_id=contact.id, status="open",
            assigned_user_id=(assigned.id if assigned else None),
            last_inbound_at=(now if expires else None),
            customer_service_window_expires_at=expires)
        db.add(conv)
        db.commit()
        return conv

    def _seed_outbound(self, conv, status):
        """Un mensaje saliente ya existente en un estado dado (para tests de in-flight)."""
        m = models.WhatsAppMessage(
            conversation_id=conv.id, provider="meta", direction="outbound",
            message_type="text", text_body="previo", current_status=status, origin="crm",
            client_request_id=uuid.uuid4())
        self.db.add(m)
        self.db.commit()
        return m

    def _post(self, conv_id, text, *, crid=None, user=None, message_type="text"):
        if user is not None:
            self.as_user(user)
        body = {"message_type": message_type, "text": text,
                "client_request_id": str(crid or uuid.uuid4())}
        return self.client.post(f"/whatsapp/conversations/{conv_id}/messages", json=body)

    def _msgs(self, conv_id):
        return (self.db.query(models.WhatsAppMessage)
                .filter(models.WhatsAppMessage.conversation_id == conv_id).all())


# =============================================================================== #
# Feature flag, permisos, validación
# =============================================================================== #
class FlagAndAuthTests(OutboundTestBase):
    def test_01_disabled_returns_503_no_row(self):
        os.environ[WA_ENV] = "false"
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_DISABLED)
        self.assertEqual(len(self._msgs(conv.id)), 0)
        self.assertEqual(len(self.sender.calls), 0)

    def test_02_admin_allowed(self):
        conv = self._make_conv()
        r = self._post(conv.id, "hola admin", user=self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["accepted"])
        self.assertEqual(r.json()["outcome"], "accepted")

    def test_03_seller_authorized_with_can_send(self):
        conv = self._make_conv(assigned=self.seller)
        r = self._post(conv.id, "hola", user=self.seller)
        self.assertEqual(r.status_code, 201)

    def test_04_seller_unauthorized_conversation_404(self):
        conv = self._make_conv()  # no asignada, seller_none sin acceso a la línea
        r = self._post(conv.id, "hola", user=self.seller_none)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_NOT_FOUND)
        self.assertEqual(len(self._msgs(conv.id)), 0)

    def test_05_seller_can_send_false_403(self):
        # seller_view tiene can_view pero can_send=False en la línea.
        conv = self._make_conv(assigned=self.seller_view)
        r = self._post(conv.id, "hola", user=self.seller_view)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_FORBIDDEN)
        self.assertEqual(len(self._msgs(conv.id)), 0)

    def test_06_inactive_line_409(self):
        conv = self._make_conv(line=self.line_inactive)  # admin accede a todo
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_LINE_INACTIVE)


class TextValidationTests(OutboundTestBase):
    def test_07_empty_text(self):
        conv = self._make_conv()
        r = self._post(conv.id, "", user=self.admin)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_TEXT_EMPTY)

    def test_08_whitespace_only(self):
        conv = self._make_conv()
        r = self._post(conv.id, "   \n\t  ", user=self.admin)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_TEXT_EMPTY)

    def test_09_crlf_normalization_persisted(self):
        conv = self._make_conv()
        r = self._post(conv.id, "linea1\r\nlinea2\rlinea3", user=self.admin)
        self.assertEqual(r.status_code, 201)
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.text_body, "linea1\nlinea2\nlinea3")
        self.assertNotIn("\r", msg.text_body)

    def test_10_text_too_long(self):
        conv = self._make_conv()
        r = self._post(conv.id, "a" * 4097, user=self.admin)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_TEXT_TOO_LONG)

    def test_10b_text_exactly_max_ok(self):
        conv = self._make_conv()
        r = self._post(conv.id, "a" * 4096, user=self.admin)
        self.assertEqual(r.status_code, 201)


class WindowTests(OutboundTestBase):
    def test_11_window_open(self):
        conv = self._make_conv(window="open")
        r = self._post(conv.id, "dentro de ventana", user=self.admin)
        self.assertEqual(r.status_code, 201)

    def test_12_window_closed(self):
        conv = self._make_conv(window="closed")
        r = self._post(conv.id, "fuera de ventana", user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_TEMPLATE_REQUIRED)

    def test_13_window_null(self):
        conv = self._make_conv(window="null")
        r = self._post(conv.id, "sin ventana", user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_TEMPLATE_REQUIRED)


class RecipientTests(OutboundTestBase):
    def test_14_wa_id_primary(self):
        conv = self._make_conv(wa_id_primary=WA_ID_PRIMARY)
        self.assertEqual(ob.resolve_meta_recipient(self.db, conv.contact_id), WA_ID_PRIMARY)

    def test_15_fallback_wa_id_non_primary(self):
        conv = self._make_conv(wa_id_primary=None, wa_id=WA_ID_SECONDARY)
        self.assertEqual(ob.resolve_meta_recipient(self.db, conv.contact_id), WA_ID_SECONDARY)

    def test_16_fallback_phone_e164_primary(self):
        conv = self._make_conv(wa_id_primary=None, phone_primary=PHONE_E164)
        self.assertEqual(ob.resolve_meta_recipient(self.db, conv.contact_id), PHONE_E164)

    def test_17_no_recipient_409(self):
        conv = self._make_conv(wa_id_primary=None)  # sin identificadores
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_RECIPIENT_UNAVAILABLE)
        self.assertEqual(len(self._msgs(conv.id)), 0)


# =============================================================================== #
# Resultado del sender
# =============================================================================== #
class SenderResultTests(OutboundTestBase):
    def test_18_accepted_sets_external_id(self):
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["outcome"], "accepted")
        # external_message_id NO se expone, pero SÍ se persiste.
        self.assertNotIn("external_message_id", r.json()["message"])
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.current_status, "accepted")
        self.assertEqual(msg.external_message_id, FAKE_WAMID)
        self.assertEqual(len(self.sender.calls), 1)

    def test_19_definitive_failure(self):
        self.sender.result = SendResult(
            outcome=OUTCOME_DEFINITIVE_FAILURE, error_code="131026",
            error_message_safe="undeliverable")
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["accepted"])
        self.assertEqual(r.json()["outcome"], "failed")
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.current_status, "failed")
        self.assertEqual(msg.error_code, "131026")
        self.assertIsNone(msg.external_message_id)

    def test_20_ambiguous_becomes_unknown(self):
        self.sender.result = SendResult(outcome=OUTCOME_AMBIGUOUS)
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 202)
        self.assertFalse(r.json()["accepted"])
        self.assertEqual(r.json()["outcome"], "unknown")
        self.assertEqual(self._msgs(conv.id)[0].current_status, "unknown")

    def test_20b_sender_crash_becomes_unknown(self):
        self.sender.raises = RuntimeError("read timeout con texto secreto")
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(self._msgs(conv.id)[0].current_status, "unknown")


# =============================================================================== #
# Idempotencia
# =============================================================================== #
class IdempotencyTests(OutboundTestBase):
    def test_21_replay_accepted(self):
        conv = self._make_conv()
        crid = uuid.uuid4()
        r1 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r1.status_code, 201)
        r2 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["duplicate"])
        self.assertEqual(r2.json()["outcome"], "accepted")
        self.assertEqual(len(self._msgs(conv.id)), 1)      # una sola fila
        self.assertEqual(len(self.sender.calls), 1)         # una sola invocación

    def test_22_replay_unknown_does_not_reinvoke(self):
        self.sender.result = SendResult(outcome=OUTCOME_AMBIGUOUS)
        conv = self._make_conv()
        crid = uuid.uuid4()
        r1 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r1.status_code, 202)
        r2 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["duplicate"])
        self.assertEqual(r2.json()["outcome"], "unknown")
        self.assertEqual(len(self.sender.calls), 1)         # NO se reinvoca en unknown

    def test_23_same_uuid_different_text_mismatch(self):
        conv = self._make_conv()
        crid = uuid.uuid4()
        self._post(conv.id, "texto original", crid=crid, user=self.admin)
        r = self._post(conv.id, "texto distinto", crid=crid, user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_MISMATCH)
        self.assertEqual(len(self.sender.calls), 1)

    def test_24_same_uuid_different_conversation_mismatch(self):
        conv1 = self._make_conv()
        conv2 = self._make_conv()
        crid = uuid.uuid4()
        self._post(conv1.id, "hola", crid=crid, user=self.admin)
        r = self._post(conv2.id, "hola", crid=crid, user=self.admin)
        # No filtra info de otra conversación: mismatch controlado (409).
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_MISMATCH)


# =============================================================================== #
# Una salida en vuelo por conversación
# =============================================================================== #
class SingleInflightTests(OutboundTestBase):
    def _assert_blocked(self, status):
        conv = self._make_conv()
        self._seed_outbound(conv, status)
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["detail"]["code"], ob.CODE_IN_PROGRESS)
        self.assertEqual(len(self.sender.calls), 0)

    def test_27_pending_blocks(self):
        self._assert_blocked("pending")

    def test_28_sending_blocks(self):
        self._assert_blocked("sending")

    def test_29_unknown_blocks(self):
        self._assert_blocked("unknown")

    def test_30_accepted_does_not_block(self):
        conv = self._make_conv()
        self._seed_outbound(conv, "accepted")
        r = self._post(conv.id, "otra", user=self.admin)
        self.assertEqual(r.status_code, 201)

    def test_31_failed_does_not_block(self):
        conv = self._make_conv()
        self._seed_outbound(conv, "failed")
        r = self._post(conv.id, "otra", user=self.admin)
        self.assertEqual(r.status_code, 201)


# =============================================================================== #
# Resultado tardío / logs
# =============================================================================== #
class LateResultAndLogTests(OutboundTestBase):
    def test_32_late_result_does_not_regress_delivered(self):
        # El mensaje ya está 'delivered' (p. ej. webhook adelantado): aplicar 'accepted'
        # tardío NO debe retroceder el estado.
        conv = self._make_conv()
        msg = self._seed_outbound(conv, "delivered")
        ob.apply_result(self.db, msg.id,
                        SendResult(outcome=OUTCOME_ACCEPTED, external_message_id="wamid.X"))
        self.db.refresh(msg)
        self.assertEqual(msg.current_status, "delivered")

    def test_32b_late_failure_does_not_regress_read(self):
        conv = self._make_conv()
        msg = self._seed_outbound(conv, "read")
        ob.apply_result(self.db, msg.id,
                        SendResult(outcome=OUTCOME_DEFINITIVE_FAILURE, error_code="1"))
        self.db.refresh(msg)
        self.assertEqual(msg.current_status, "read")

    def test_33_logs_have_no_sensitive_content(self):
        conv = self._make_conv(wa_id_primary=WA_ID_PRIMARY)
        secret_text = "contenido-confidencial-del-mensaje"
        with self.assertLogs("uvicorn.error", level="INFO") as cm:
            r = self._post(conv.id, secret_text, user=self.admin)
        self.assertEqual(r.status_code, 201)
        joined = "\n".join(cm.output)
        for forbidden in (secret_text, WA_ID_PRIMARY, "admin@test.local"):
            self.assertNotIn(forbidden, joined)


# =============================================================================== #
# 1I.1b — sanitización de excepciones del sender + accepted sin wamid + outcome inválido
# =============================================================================== #
class HardeningSenderTests(OutboundTestBase):
    def test_h01_sender_exception_logs_sanitized(self):
        secret_text = "texto-secreto-del-mensaje"
        fake_phone = "5491199999999"
        fake_token = "EAAG_fake_token_zzz"
        fake_url = "https://graph.facebook.com/vXX/PNID/messages"
        self.sender.raises = RuntimeError(
            f"boom text={secret_text} to={fake_phone} token={fake_token} url={fake_url}")
        conv = self._make_conv()
        with self.assertLogs("uvicorn.error", level="INFO") as cm:
            r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["outcome"], "unknown")
        joined = "\n".join(cm.output)
        for forbidden in (secret_text, fake_phone, fake_token, fake_url):
            self.assertNotIn(forbidden, joined)
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.current_status, "unknown")
        self.assertEqual(msg.error_code, ob.CODE_SENDER_EXCEPTION)
        self.assertEqual(msg.error_message_safe, "outbound result is ambiguous")

    def test_h02_accepted_valid_wamid(self):
        self.sender.result = SendResult(outcome=OUTCOME_ACCEPTED, external_message_id=FAKE_WAMID)
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self._msgs(conv.id)[0].external_message_id, FAKE_WAMID)

    def _accepted_without_id(self, ext):
        self.sender.result = SendResult(outcome=OUTCOME_ACCEPTED, external_message_id=ext)
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["outcome"], "unknown")
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.current_status, "unknown")
        self.assertEqual(msg.error_code, ob.CODE_ACCEPTED_NO_EXTERNAL_ID)
        self.assertIsNone(msg.external_message_id)

    def test_h03_accepted_none_unknown(self):
        self._accepted_without_id(None)

    def test_h04_accepted_empty_unknown(self):
        self._accepted_without_id("")

    def test_h05_accepted_whitespace_unknown(self):
        self._accepted_without_id("   \t ")

    def test_h06_replay_of_accepted_without_id_no_reinvoke(self):
        self.sender.result = SendResult(outcome=OUTCOME_ACCEPTED, external_message_id=None)
        conv = self._make_conv()
        crid = uuid.uuid4()
        r1 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r1.status_code, 202)
        r2 = self._post(conv.id, "hola", crid=crid, user=self.admin)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["duplicate"])
        self.assertEqual(r2.json()["outcome"], "unknown")
        self.assertEqual(len(self.sender.calls), 1)

    def test_h07_invalid_outcome_becomes_unknown(self):
        self.sender.result = SendResult(outcome="outcome_desconocido")
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["outcome"], "unknown")
        msg = self._msgs(conv.id)[0]
        self.assertEqual(msg.current_status, "unknown")
        self.assertEqual(msg.error_code, ob.CODE_INVALID_RESULT)


# =============================================================================== #
# 1I.1b — resolución con múltiples identificadores
# =============================================================================== #
class RecipientMultiCandidateTests(OutboundTestBase):
    V_WA_A = "5491100000010"
    V_WA_B = "5491100000011"
    V_PHONE_A = "+5491100000012"
    V_PHONE_B = "+5491100000013"
    INVALID = "no-es-numero"

    def _contact(self, idents):
        c = models.WhatsAppContact(display_name="multi")
        self.db.add(c)
        self.db.flush()
        for itype, value, primary in idents:
            self.db.add(models.WhatsAppContactIdentifier(
                contact_id=c.id, provider="meta", identifier_type=itype,
                identifier_value=value, is_primary=primary))
        self.db.commit()
        return c.id

    def test_r01_first_wa_id_invalid_second_valid(self):
        cid = self._contact([("wa_id", self.INVALID, False), ("wa_id", self.V_WA_A, False)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_WA_A)

    def test_r02_primary_invalid_nonprimary_valid(self):
        cid = self._contact([("wa_id", self.INVALID, True), ("wa_id", self.V_WA_A, False)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_WA_A)

    def test_r03_phone_primary_invalid_second_primary_valid(self):
        cid = self._contact([("phone_e164", "+abc", True), ("phone_e164", self.V_PHONE_A, True)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_PHONE_A)

    def test_r04_wa_id_beats_phone(self):
        cid = self._contact([("phone_e164", self.V_PHONE_A, True), ("wa_id", self.V_WA_A, False)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_WA_A)

    def test_r05_deterministic_order_by_id(self):
        cid = self._contact([("wa_id", self.V_WA_A, False), ("wa_id", self.V_WA_B, False)])
        # el primero insertado (id menor) gana
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_WA_A)

    def test_r06_phone_e164_normalizer_format_accepted(self):
        # Formato REAL del normalizer: `+`+dígitos.
        cid = self._contact([("phone_e164", self.V_PHONE_A, True)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), self.V_PHONE_A)

    def test_r06b_phone_e164_digits_only_accepted(self):
        # Formato histórico tolerado: solo dígitos, sin `+` (no se modifica el valor).
        cid = self._contact([("phone_e164", "5491100000014", True)])
        self.assertEqual(ob.resolve_meta_recipient(self.db, cid), "5491100000014")


# =============================================================================== #
# 1I.1b — CAS pending → sending obligatorio
# =============================================================================== #
class CasTests(OutboundTestBase):
    def test_c01_cas_success_one_invocation(self):
        conv = self._make_conv()
        r = self._post(conv.id, "hola", user=self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(self._msgs(conv.id)[0].current_status, "accepted")

    def test_c02_cas_forced_fail_zero_invocations(self):
        conv = self._make_conv()
        with mock.patch("app.services.whatsapp.outbound._cas_pending_to_sending",
                        return_value=False):
            r = self._post(conv.id, "hola", user=self.admin)
        # CAS perdido ⇒ Replay sin enviar (el mensaje queda pending, sin invocar al sender).
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["duplicate"])
        self.assertEqual(len(self.sender.calls), 0)
        self.assertEqual(self._msgs(conv.id)[0].current_status, "pending")

    def test_c03_cas_helper_pending_ok(self):
        conv = self._make_conv()
        msg = self._seed_outbound(conv, "pending")
        self.assertTrue(ob._cas_pending_to_sending(self.db, msg.id))
        self.db.refresh(msg)
        self.assertEqual(msg.current_status, "sending")

    def test_c04_cas_helper_delivered_no_effect(self):
        conv = self._make_conv()
        msg = self._seed_outbound(conv, "delivered")
        self.assertFalse(ob._cas_pending_to_sending(self.db, msg.id))
        self.db.refresh(msg)
        self.assertEqual(msg.current_status, "delivered")

    def test_c05_cas_helper_failed_no_effect(self):
        conv = self._make_conv()
        msg = self._seed_outbound(conv, "failed")
        self.assertFalse(ob._cas_pending_to_sending(self.db, msg.id))
        self.db.refresh(msg)
        self.assertEqual(msg.current_status, "failed")


# =============================================================================== #
# Concurrencia REAL en PostgreSQL 17 (gated). FOR UPDATE no se puede validar en SQLite.
# =============================================================================== #
@unittest.skipUnless(os.getenv("WHATSAPP_OUTBOUND_PG_DSN"),
                     "requiere WHATSAPP_OUTBOUND_PG_DSN (PostgreSQL 17 efímero)")
class PgConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(os.environ["WHATSAPP_OUTBOUND_PG_DSN"], future=True)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

    def setUp(self):
        # El esquema lo crea `alembic upgrade head` (harness externo). Cada test limpia y
        # siembra su propia conversación/usuario.
        db = self.Session()
        try:
            for t in ("whatsapp_message_status_events", "whatsapp_messages",
                      "whatsapp_conversation_reads", "whatsapp_conversation_assignments",
                      "whatsapp_conversations", "whatsapp_contact_identifiers",
                      "whatsapp_contacts", "whatsapp_line_user_access", "whatsapp_lines"):
                db.execute(text(f"DELETE FROM {t}"))
            db.execute(text("DELETE FROM users WHERE email = 'pg_admin@test.local'"))
            db.commit()
            line = models.WhatsAppLine(provider="meta", phone_number_id="PG_PNID",
                                       waba_id="PG_WABA", display_number="+540000009999",
                                       label="PG", is_active=True)
            db.add(line)
            self.user = models.User(email="pg_admin@test.local", hashed_password="x",
                                    full_name="PG Admin", role="admin")
            db.add(self.user)
            db.flush()
            self.user_id = self.user.id
            contact = models.WhatsAppContact(display_name="PG Contact")
            db.add(contact)
            db.flush()
            db.add(models.WhatsAppContactIdentifier(
                contact_id=contact.id, provider="meta", identifier_type="wa_id",
                identifier_value=WA_ID_PRIMARY, is_primary=True))
            conv = models.WhatsAppConversation(
                line_id=line.id, contact_id=contact.id, status="open",
                customer_service_window_expires_at=datetime.now(timezone.utc) + timedelta(hours=12))
            db.add(conv)
            db.commit()
            self.conv_id = conv.id
        finally:
            db.close()

    def _run_two(self, crids):
        """Ejecuta reserve_outbound en 2 hilos (sesiones separadas) sincronizados."""
        barrier = threading.Barrier(2)
        results = [None, None]

        def worker(idx, crid):
            s = self.Session()
            try:
                barrier.wait()
                try:
                    r = ob.reserve_outbound(s, s.get(models.User, self.user_id), self.conv_id,
                                            message_type="text", text="hola concurrente",
                                            client_request_id=crid)
                    results[idx] = ("ok", type(r).__name__)
                except ob.OutboundError as e:
                    results[idx] = ("err", e.code)
            finally:
                s.close()

        threads = [threading.Thread(target=worker, args=(i, crids[i])) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def _count_msgs(self):
        db = self.Session()
        try:
            return db.query(models.WhatsAppMessage).filter(
                models.WhatsAppMessage.conversation_id == self.conv_id).count()
        finally:
            db.close()

    def test_pg_same_crid_one_row(self):
        crid = uuid.uuid4()
        results = self._run_two([crid, crid])
        kinds = sorted(r[1] for r in results)
        # Uno reserva, el otro es replay idempotente; una sola fila.
        self.assertEqual(kinds, ["Replay", "Reserved"])
        self.assertEqual(self._count_msgs(), 1)

    def test_pg_two_crid_one_blocked(self):
        results = self._run_two([uuid.uuid4(), uuid.uuid4()])
        codes = sorted(str(r[1]) for r in results)
        # Uno reserva; el otro se bloquea por "una salida en vuelo".
        self.assertEqual(codes, sorted([ob.CODE_IN_PROGRESS, "Reserved"]))
        self.assertEqual(self._count_msgs(), 1)

    def test_pg_full_flow_concurrent_single_sender_call(self):
        """Flujo COMPLETO por el endpoint: dos requests concurrentes (crids distintos) →
        una sola reserva efectiva, UNA sola invocación del sender, y el otro request
        recibe 409 WHATSAPP_SEND_IN_PROGRESS. El sender demora (`delay`) para que el
        mensaje ganador siga en vuelo cuando el perdedor consulta (determinista)."""
        s = self.Session()
        admin = s.get(models.User, self.user_id)
        s.expunge(admin)   # desprendido: atributos ya cargados, sin lazy-load
        s.close()

        session_local = self.Session
        fake = FakeWhatsAppSender(delay=0.5)

        def get_db_override():
            db = session_local()
            try:
                yield db
            finally:
                db.close()

        app = FastAPI()
        app.include_router(whatsapp_inbox.router)
        app.dependency_overrides[database.get_db] = get_db_override
        app.dependency_overrides[whatsapp_inbox.get_whatsapp_sender] = lambda: fake
        app.dependency_overrides[get_current_user] = lambda: admin
        os.environ[WA_ENV] = "true"
        try:
            barrier = threading.Barrier(2)
            statuses = [None, None]

            def worker(idx):
                async def _do():
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://t") as ac:
                        barrier.wait()
                        return await ac.post(
                            f"/whatsapp/conversations/{self.conv_id}/messages",
                            json={"message_type": "text", "text": "concurrente",
                                  "client_request_id": str(uuid.uuid4())})
                statuses[idx] = asyncio.run(_do()).status_code

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(sorted(statuses), [201, 409])
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(self._count_msgs(), 1)
        finally:
            os.environ.pop(WA_ENV, None)


if __name__ == "__main__":
    unittest.main()

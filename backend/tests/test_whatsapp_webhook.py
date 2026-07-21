"""
Tests del webhook de WhatsApp Cloud API — Etapa 1C (fundación de recepción).

Aislado y sin tocar ninguna base real:
- SQLite en memoria (StaticPool) con `PRAGMA foreign_keys=ON`, esquema creado desde
  `Base.metadata` (Alembic sigue siendo el único gestor del esquema PostgreSQL).
- NO importa `app.main`: se arma una FastAPI mínima con el router de WhatsApp y se
  sobrescribe `app.database.get_db` para apuntar a la sesión SQLite de test.
- Secretos ficticios inyectados por entorno (`WHATSAPP_VERIFY_TOKEN`,
  `WHATSAPP_META_APP_SECRET`); nunca se conecta a Meta ni se envía nada.

Framework: `unittest` (stdlib), igual que el resto de la suite del backend.

    python -m unittest tests.test_whatsapp_webhook -v
"""

import asyncio
import json
import os
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests import whatsapp_fixtures as fx

# El entorno se fija ANTES de importar la app: los servicios lo leen en tiempo de
# llamada, pero así queda explícito que el webhook no funciona sin configuración.
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", fx.TEST_VERIFY_TOKEN)
os.environ.setdefault("WHATSAPP_META_APP_SECRET", fx.TEST_APP_SECRET)

from app import database, models  # noqa: E402
from app.database import Base  # noqa: E402
from app.routers import whatsapp as whatsapp_router  # noqa: E402
from app.services.whatsapp import config as wa_config  # noqa: E402
from app.services.whatsapp import events as wa_events  # noqa: E402
from app.services.whatsapp import processor as wa_processor  # noqa: E402
from app.services.whatsapp import normalizer as wa_normalizer  # noqa: E402
from app.services.whatsapp.redaction import mask_identifier, safe_error, short_key  # noqa: E402
from app.services.whatsapp.signature import compute_signature, verify_signature  # noqa: E402

WEBHOOK_URL = "/whatsapp/webhook"
LOGGER_NAME = "uvicorn.error"


class _ASGIClient:
    """
    Cliente HTTP síncrono mínimo sobre httpx.ASGITransport (mismo helper que usa
    `tests/test_security_phase0a.py`: httpx >= 0.28 quitó el atajo `app=`).
    """

    def __init__(self, app):
        self._app = app

    def _request(self, method, url, **kwargs):
        async def _do():
            transport = ASGITransport(app=self._app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                return await ac.request(method, url, **kwargs)
        return asyncio.run(_do())

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._request("PUT", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._request("DELETE", url, **kwargs)


# =============================================================================== #
# Tests unitarios puros (sin base ni HTTP)
# =============================================================================== #
class SignatureUnitTest(unittest.TestCase):
    """Validación HMAC-SHA256 aislada del router."""

    SECRET = fx.TEST_APP_SECRET
    BODY = b'{"object":"whatsapp_business_account"}'

    def test_valid_signature(self):
        sig = compute_signature(self.SECRET, self.BODY)
        self.assertTrue(verify_signature(self.SECRET, self.BODY, sig))

    def test_signature_is_lowercase_hex_with_prefix(self):
        sig = compute_signature(self.SECRET, self.BODY)
        self.assertTrue(sig.startswith("sha256="))
        self.assertEqual(len(sig), len("sha256=") + 64)

    def test_missing_header_rejected(self):
        self.assertFalse(verify_signature(self.SECRET, self.BODY, ""))
        self.assertFalse(verify_signature(self.SECRET, self.BODY, None))

    def test_wrong_prefix_rejected(self):
        digest = compute_signature(self.SECRET, self.BODY).split("=", 1)[1]
        self.assertFalse(verify_signature(self.SECRET, self.BODY, f"sha1={digest}"))
        self.assertFalse(verify_signature(self.SECRET, self.BODY, digest))

    def test_invalid_digest_rejected(self):
        self.assertFalse(verify_signature(self.SECRET, self.BODY, "sha256=nohexvalue"))
        self.assertFalse(verify_signature(self.SECRET, self.BODY, "sha256="))
        self.assertFalse(verify_signature(self.SECRET, self.BODY, "sha256=" + "0" * 64))

    def test_body_tampered_after_signing_rejected(self):
        sig = compute_signature(self.SECRET, self.BODY)
        self.assertFalse(verify_signature(self.SECRET, self.BODY + b" ", sig))

    def test_other_secret_rejected(self):
        sig = compute_signature("otro-secreto", self.BODY)
        self.assertFalse(verify_signature(self.SECRET, self.BODY, sig))

    def test_empty_secret_never_validates(self):
        sig = compute_signature("", self.BODY)
        self.assertFalse(verify_signature("", self.BODY, sig))


class NormalizerUnitTest(unittest.TestCase):
    """Claves determinísticas y normalización tolerante."""

    def test_event_key_is_deterministic_and_content_based(self):
        payload = fx.text_message_event()
        k1 = wa_normalizer.normalize_envelope(payload).event_key
        k2 = wa_normalizer.normalize_envelope(json.loads(json.dumps(payload))).event_key
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("sha256:"))

    def test_event_key_ignores_key_order(self):
        payload = fx.text_message_event()
        reordered = json.loads(json.dumps(payload, sort_keys=True))
        self.assertEqual(
            wa_normalizer.normalize_envelope(payload).event_key,
            wa_normalizer.normalize_envelope(reordered).event_key,
        )

    def test_event_key_changes_with_content(self):
        a = wa_normalizer.normalize_envelope(fx.text_message_event(body="uno")).event_key
        b = wa_normalizer.normalize_envelope(fx.text_message_event(body="dos")).event_key
        self.assertNotEqual(a, b)

    def test_event_key_fits_column(self):
        norm = wa_normalizer.normalize_envelope(fx.text_message_event())
        self.assertLessEqual(len(norm.event_key), 255)
        self.assertEqual(len(norm.payload_hash), 64)

    def test_status_event_key_is_stable(self):
        k1 = wa_normalizer.build_status_event_key("wamid.X", "read", "1700000000")
        k2 = wa_normalizer.build_status_event_key("wamid.X", "read", "1700000000")
        k3 = wa_normalizer.build_status_event_key("wamid.X", "delivered", "1700000000")
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertLessEqual(len(k1), 255)

    def test_status_event_key_long_ids_are_hashed(self):
        key = wa_normalizer.build_status_event_key("wamid." + "X" * 400, "read", "1700000000")
        self.assertLessEqual(len(key), 255)
        self.assertIn("sha256:", key)

    def test_unknown_extra_fields_do_not_break(self):
        payload = fx.text_message_event()
        payload["entry"][0]["changes"][0]["value"]["campo_nuevo_de_meta"] = {"x": 1}
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["futuro"] = True
        norm = wa_normalizer.normalize_envelope(payload)
        self.assertEqual(norm.total_messages, 1)
        self.assertTrue(norm.changes[0].messages[0].supported)

    def test_non_dict_payload_is_ignored_not_fatal(self):
        norm = wa_normalizer.normalize_envelope([1, 2, 3])
        self.assertFalse(norm.supported_object)
        self.assertEqual(norm.changes, [])

    def test_timestamp_parsing(self):
        self.assertEqual(
            wa_normalizer.parse_provider_timestamp("1700000000"),
            datetime.fromtimestamp(1700000000, tz=timezone.utc),
        )
        self.assertIsNone(wa_normalizer.parse_provider_timestamp("no-numerico"))
        self.assertIsNone(wa_normalizer.parse_provider_timestamp(None))

    def test_wa_id_to_e164(self):
        self.assertEqual(wa_normalizer.normalize_wa_id_to_e164("5491100000000"), "+5491100000000")
        self.assertEqual(wa_normalizer.normalize_wa_id_to_e164("+5491100000000"), "+5491100000000")
        self.assertIsNone(wa_normalizer.normalize_wa_id_to_e164("no-es-numero"))
        self.assertIsNone(wa_normalizer.normalize_wa_id_to_e164("123"))
        self.assertIsNone(wa_normalizer.normalize_wa_id_to_e164(None))


class StatusPrecedenceUnitTest(unittest.TestCase):
    """Precedencia explícita de estados (`pending < sent < delivered < read`)."""

    def test_forward_progression(self):
        self.assertEqual(wa_processor.next_current_status("pending", "sent"), "sent")
        self.assertEqual(wa_processor.next_current_status("sent", "delivered"), "delivered")
        self.assertEqual(wa_processor.next_current_status("delivered", "read"), "read")

    def test_never_goes_backwards(self):
        self.assertEqual(wa_processor.next_current_status("read", "delivered"), "read")
        self.assertEqual(wa_processor.next_current_status("read", "sent"), "read")
        self.assertEqual(wa_processor.next_current_status("delivered", "sent"), "delivered")

    def test_failed_rules(self):
        self.assertEqual(wa_processor.next_current_status("sent", "failed"), "failed")
        self.assertEqual(wa_processor.next_current_status("pending", "failed"), "failed")
        # Con prueba de entrega, un `failed` fuera de orden no pisa el estado real.
        self.assertEqual(wa_processor.next_current_status("delivered", "failed"), "delivered")
        self.assertEqual(wa_processor.next_current_status("read", "failed"), "read")
        # Desde failed solo una confirmación real de entrega/lectura puede superarlo.
        self.assertEqual(wa_processor.next_current_status("failed", "sent"), "failed")
        self.assertEqual(wa_processor.next_current_status("failed", "delivered"), "delivered")

    def test_empty_status_keeps_current(self):
        self.assertEqual(wa_processor.next_current_status("sent", None), "sent")


class RedactionUnitTest(unittest.TestCase):
    """Los helpers de logging no pueden filtrar datos completos."""

    def test_mask_identifier(self):
        masked = mask_identifier(fx.TEST_WA_ID)
        self.assertNotIn(fx.TEST_WA_ID, masked)
        self.assertTrue(masked.startswith("***"))
        self.assertEqual(mask_identifier(""), "***")
        self.assertEqual(mask_identifier("123"), "***")

    def test_short_key_truncates(self):
        self.assertLessEqual(len(short_key("a" * 100, 12)), 13)

    def test_safe_error_is_single_line_and_bounded(self):
        msg = safe_error(RuntimeError("linea 1\nlinea 2   con   espacios " + "x" * 500))
        self.assertNotIn("\n", msg)
        self.assertLessEqual(len(msg), 200)


# =============================================================================== #
# Base común de los tests de integración HTTP
# =============================================================================== #
class WebhookTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # FKs reales en SQLite: sin esto las violaciones de integridad no se detectan
        # y los tests de rollback/duplicados no probarían nada.
        @event.listens_for(cls.engine, "connect")
        def _fk_pragma(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        app = FastAPI()
        app.include_router(whatsapp_router.router)

        def _get_test_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[database.get_db] = _get_test_db
        cls.app = app
        cls.client = _ASGIClient(app)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        os.environ["WHATSAPP_VERIFY_TOKEN"] = fx.TEST_VERIFY_TOKEN
        os.environ["WHATSAPP_META_APP_SECRET"] = fx.TEST_APP_SECRET

    # --- helpers ---------------------------------------------------------------
    def _session(self):
        return self.Session()

    def _seed_line(self, phone_number_id=fx.TEST_PHONE_NUMBER_ID,
                   display_number=fx.TEST_DISPLAY_NUMBER, label="Línea de test", is_active=True):
        db = self._session()
        try:
            line = models.WhatsAppLine(
                provider="meta",
                phone_number_id=phone_number_id,
                waba_id=fx.TEST_WABA_ID,
                display_number=display_number,
                label=label,
                is_active=is_active,
            )
            db.add(line)
            db.commit()
            db.refresh(line)
            return line.id
        finally:
            db.close()

    def _seed_outbound_message(self, line_id, external_id=fx.TEST_OUTBOUND_MESSAGE_ID,
                               current_status="pending"):
        """Mensaje saliente ya existente, para los tests de estados."""
        db = self._session()
        try:
            contact = models.WhatsAppContact(display_name=None)
            db.add(contact)
            db.flush()
            db.add(models.WhatsAppContactIdentifier(
                contact_id=contact.id, provider="meta",
                identifier_type="wa_id", identifier_value=fx.TEST_WA_ID, is_primary=True,
            ))
            conversation = models.WhatsAppConversation(
                line_id=line_id, contact_id=contact.id, status="open",
            )
            db.add(conversation)
            db.flush()
            message = models.WhatsAppMessage(
                conversation_id=conversation.id,
                provider="meta",
                external_message_id=external_id,
                direction="outbound",
                message_type="text",
                text_body="mensaje saliente de prueba",
                current_status=current_status,
                origin="crm",
            )
            db.add(message)
            db.commit()
            return message.id
        finally:
            db.close()

    def _post(self, payload, *, secret=fx.TEST_APP_SECRET, signature=None,
              raw=None, headers=None):
        """POST firmado sobre el cuerpo CRUDO (igual que Meta)."""
        body = raw if raw is not None else json.dumps(payload).encode("utf-8")
        sent_headers = {"Content-Type": "application/json"}
        if signature is not None:
            if signature != "":
                sent_headers["X-Hub-Signature-256"] = signature
        else:
            sent_headers["X-Hub-Signature-256"] = compute_signature(secret, body)
        if headers:
            sent_headers.update(headers)
        return self.client.post(WEBHOOK_URL, content=body, headers=sent_headers)

    def _count(self, model):
        db = self._session()
        try:
            return db.query(model).count()
        finally:
            db.close()

    def _first(self, model):
        db = self._session()
        try:
            return db.query(model).first()
        finally:
            db.close()

    def _events(self):
        db = self._session()
        try:
            return db.query(models.WhatsAppWebhookEvent).all()
        finally:
            db.close()


# =============================================================================== #
# GET — verificación del webhook
# =============================================================================== #
class WebhookVerificationTest(WebhookTestBase):
    def _get(self, **params):
        query = {f"hub.{k}": v for k, v in params.items() if v is not None}
        return self.client.get(WEBHOOK_URL, params=query)

    def test_valid_challenge_returns_200_and_echo(self):
        r = self._get(mode="subscribe", verify_token=fx.TEST_VERIFY_TOKEN, challenge="1234567890")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.text, "1234567890")

    def test_invalid_token_returns_403(self):
        r = self._get(mode="subscribe", verify_token="token-incorrecto", challenge="123")
        self.assertEqual(r.status_code, 403)

    def test_invalid_mode_returns_403(self):
        r = self._get(mode="unsubscribe", verify_token=fx.TEST_VERIFY_TOKEN, challenge="123")
        self.assertEqual(r.status_code, 403)

    def test_missing_params_are_controlled(self):
        self.assertEqual(self._get().status_code, 403)
        self.assertEqual(self._get(mode="subscribe").status_code, 403)
        self.assertEqual(self._get(mode="subscribe", challenge="123").status_code, 403)
        self.assertEqual(
            self._get(mode="subscribe", verify_token=fx.TEST_VERIFY_TOKEN).status_code, 403)

    def test_response_never_contains_the_token(self):
        r = self._get(mode="subscribe", verify_token=fx.TEST_VERIFY_TOKEN, challenge="123")
        self.assertNotIn(fx.TEST_VERIFY_TOKEN, r.text)
        r2 = self._get(mode="subscribe", verify_token="token-incorrecto", challenge="123")
        self.assertNotIn(fx.TEST_VERIFY_TOKEN, r2.text)

    def test_verify_token_never_reaches_the_logs(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured:
            self._get(mode="subscribe", verify_token=fx.TEST_VERIFY_TOKEN, challenge="123")
            self._get(mode="subscribe", verify_token="token-incorrecto", challenge="123")
        joined = "\n".join(captured.output)
        self.assertNotIn(fx.TEST_VERIFY_TOKEN, joined)
        self.assertNotIn("token-incorrecto", joined)

    def test_unconfigured_token_fails_closed(self):
        os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)
        try:
            r = self._get(mode="subscribe", verify_token="cualquiera", challenge="123")
            self.assertEqual(r.status_code, 503)
        finally:
            os.environ["WHATSAPP_VERIFY_TOKEN"] = fx.TEST_VERIFY_TOKEN

    def test_get_does_not_require_jwt(self):
        r = self._get(mode="subscribe", verify_token=fx.TEST_VERIFY_TOKEN, challenge="9")
        self.assertEqual(r.status_code, 200, r.text)


# =============================================================================== #
# POST — firma y transporte
# =============================================================================== #
class WebhookSignatureTest(WebhookTestBase):
    def setUp(self):
        super().setUp()
        self.line_id = self._seed_line()

    def test_valid_signature_accepted(self):
        r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)

    def test_missing_signature_rejected(self):
        r = self._post(fx.text_message_event(), signature="")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_invalid_signature_rejected(self):
        r = self._post(fx.text_message_event(), signature="sha256=" + "a" * 64)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_wrong_prefix_rejected(self):
        body = json.dumps(fx.text_message_event()).encode("utf-8")
        digest = compute_signature(fx.TEST_APP_SECRET, body).split("=", 1)[1]
        r = self._post(None, raw=body, signature=f"sha1={digest}")
        self.assertEqual(r.status_code, 403)

    def test_signature_from_other_secret_rejected(self):
        r = self._post(fx.text_message_event(), secret="secreto-que-no-es")
        self.assertEqual(r.status_code, 403)

    def test_body_modified_after_signing_rejected(self):
        payload = fx.text_message_event()
        body = json.dumps(payload).encode("utf-8")
        signature = compute_signature(fx.TEST_APP_SECRET, body)
        tampered = json.dumps({**payload, "inyectado": True}).encode("utf-8")
        r = self._post(None, raw=tampered, signature=signature)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_invalid_json_with_valid_signature_is_controlled(self):
        raw = b'{"object": "whatsapp_business_account", ROTO'
        r = self._post(None, raw=raw)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_unconfigured_app_secret_fails_closed(self):
        os.environ.pop("WHATSAPP_META_APP_SECRET", None)
        try:
            r = self._post(fx.text_message_event())
            self.assertEqual(r.status_code, 503)
            self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)
        finally:
            os.environ["WHATSAPP_META_APP_SECRET"] = fx.TEST_APP_SECRET

    def test_oversized_body_rejected(self):
        payload = fx.text_message_event(body="x" * (wa_config.MAX_WEBHOOK_BODY_BYTES + 1024))
        r = self._post(payload)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_secrets_never_appear_in_responses(self):
        r_ok = self._post(fx.text_message_event())
        r_bad = self._post(fx.text_message_event(), signature="sha256=" + "b" * 64)
        for response in (r_ok, r_bad):
            self.assertNotIn(fx.TEST_APP_SECRET, response.text)
            self.assertNotIn(fx.TEST_VERIFY_TOKEN, response.text)

    def test_post_does_not_require_jwt(self):
        r = self._post(fx.text_message_event(), headers={"Authorization": "Bearer token-basura"})
        self.assertEqual(r.status_code, 200, r.text)

    def test_only_get_and_post_are_allowed(self):
        body = json.dumps(fx.text_message_event()).encode("utf-8")
        headers = {"X-Hub-Signature-256": compute_signature(fx.TEST_APP_SECRET, body)}
        self.assertEqual(self.client.put(WEBHOOK_URL, content=body, headers=headers).status_code, 405)
        self.assertEqual(self.client.patch(WEBHOOK_URL, content=body, headers=headers).status_code, 405)
        self.assertEqual(self.client.delete(WEBHOOK_URL, headers=headers).status_code, 405)


# =============================================================================== #
# POST — mensajes entrantes
# =============================================================================== #
class WebhookInboundMessageTest(WebhookTestBase):
    def setUp(self):
        super().setUp()
        self.line_id = self._seed_line()

    def test_text_message_creates_full_chain(self):
        r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "processed")

        db = self._session()
        try:
            evento = db.query(models.WhatsAppWebhookEvent).one()
            self.assertEqual(evento.provider, "meta")
            self.assertTrue(evento.event_key.startswith("sha256:"))
            self.assertEqual(evento.processing_status, "processed")
            self.assertEqual(evento.event_type, "messages")
            self.assertEqual(evento.attempt_count, 1)
            self.assertIsNotNone(evento.processed_at)
            self.assertIsNotNone(evento.raw_payload_expires_at)

            contacto = db.query(models.WhatsAppContact).one()
            self.assertEqual(contacto.display_name, fx.TEST_PROFILE_NAME)
            self.assertIsNone(contacto.lead_id)

            identificadores = db.query(models.WhatsAppContactIdentifier).all()
            tipos = {i.identifier_type: i.identifier_value for i in identificadores}
            self.assertEqual(tipos["wa_id"], fx.TEST_WA_ID)
            self.assertEqual(tipos["phone_e164"], f"+{fx.TEST_WA_ID}")

            conversacion = db.query(models.WhatsAppConversation).one()
            self.assertEqual(conversacion.line_id, self.line_id)
            self.assertEqual(conversacion.contact_id, contacto.id)
            self.assertEqual(conversacion.status, "open")
            self.assertIsNone(conversacion.assigned_user_id)
            self.assertIsNone(conversacion.lead_id)
            self.assertIsNotNone(conversacion.last_inbound_at)

            mensaje = db.query(models.WhatsAppMessage).one()
            self.assertEqual(mensaje.conversation_id, conversacion.id)
            self.assertEqual(mensaje.direction, "inbound")
            self.assertEqual(mensaje.message_type, "text")
            self.assertEqual(mensaje.external_message_id, fx.TEST_MESSAGE_ID)
            self.assertEqual(mensaje.text_body, "Hola, consulta de prueba")
            self.assertEqual(mensaje.current_status, "delivered")
            self.assertEqual(mensaje.origin, "cloud_api")
            self.assertIsNone(mensaje.sender_user_id)
            self.assertIsNotNone(mensaje.provider_timestamp)
        finally:
            db.close()

    def test_unknown_contact_does_not_create_lead(self):
        self._post(fx.text_message_event())
        self.assertEqual(self._count(models.Lead), 0)
        contacto = self._first(models.WhatsAppContact)
        self.assertIsNone(contacto.lead_id)
        conversacion = self._first(models.WhatsAppConversation)
        self.assertIsNone(conversacion.lead_id)

    def test_no_automatic_seller_assignment(self):
        self._post(fx.text_message_event())
        conversacion = self._first(models.WhatsAppConversation)
        self.assertIsNone(conversacion.assigned_user_id)
        self.assertIsNone(conversacion.assignment_source)
        self.assertEqual(self._count(models.WhatsAppConversationAssignment), 0)

    def test_existing_contact_and_conversation_are_reused(self):
        self._post(fx.text_message_event(message_id=fx.TEST_MESSAGE_ID))
        self._post(fx.text_message_event(message_id=fx.TEST_MESSAGE_ID_2, body="segundo"))
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        self.assertEqual(self._count(models.WhatsAppConversation), 1)
        self.assertEqual(self._count(models.WhatsAppMessage), 2)

    def test_same_person_on_another_line_uses_another_conversation(self):
        self._seed_line(phone_number_id=fx.TEST_PHONE_NUMBER_ID_B,
                        display_number=fx.TEST_DISPLAY_NUMBER_B, label="Línea B")
        self._post(fx.text_message_event(message_id=fx.TEST_MESSAGE_ID))
        self._post(fx.text_message_event(phone_number_id=fx.TEST_PHONE_NUMBER_ID_B,
                                         message_id=fx.TEST_MESSAGE_ID_2))
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        self.assertEqual(self._count(models.WhatsAppConversation), 2)
        db = self._session()
        try:
            lineas = {c.line_id for c in db.query(models.WhatsAppConversation).all()}
            self.assertEqual(len(lineas), 2)
        finally:
            db.close()

    def test_duplicate_event_is_idempotent(self):
        payload = fx.text_message_event()
        r1 = self._post(payload)
        r2 = self._post(payload)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["duplicate"])
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 1)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.attempt_count, 1)

    def test_same_message_in_a_different_event_does_not_duplicate(self):
        # Mismo wamid, envelope distinto (otro `entry.time`) => otro event_key.
        self._post(fx.text_message_event(entry_time=0))
        r = self._post(fx.text_message_event(entry_time=999))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["duplicate"])
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 2)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)
        self.assertEqual(self._count(models.WhatsAppContact), 1)
        self.assertEqual(self._count(models.WhatsAppConversation), 1)

    def test_unique_conflict_is_absorbed(self):
        """Concurrencia real: el SELECT previo no ve el duplicado y salta el unique."""
        self._post(fx.text_message_event(entry_time=1))

        real_lookup = wa_processor._find_message_by_external_id
        llamadas = {"n": 0}

        def _lookup_ciego_la_primera_vez(db, external_id):
            # 1ª llamada = SELECT de deduplicación: simula no ver la fila (carrera).
            # 2ª llamada = recuperación tras el IntegrityError: consulta real.
            llamadas["n"] += 1
            return None if llamadas["n"] == 1 else real_lookup(db, external_id)

        with mock.patch.object(wa_processor, "_find_message_by_external_id",
                               side_effect=_lookup_ciego_la_primera_vez):
            r = self._post(fx.text_message_event(entry_time=2))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)
        evento = self._events()[-1]
        self.assertEqual(evento.processing_status, "processed")

    def test_unsupported_message_type_is_safe(self):
        r = self._post(fx.unsupported_message_event(message_type="image"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "ignored")
        self.assertEqual(self._count(models.WhatsAppMessage), 0)
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.processing_status, "ignored")
        self.assertIn("unsupported_message_type", evento.last_error_safe)

    def test_every_unsupported_type_is_safe(self):
        for i, tipo in enumerate(["image", "video", "audio", "document", "sticker",
                                  "location", "contacts", "interactive", "reaction"]):
            r = self._post(fx.unsupported_message_event(
                message_type=tipo, message_id=f"wamid.TEST_UNSUPPORTED_{i}"))
            self.assertEqual(r.status_code, 200, f"{tipo}: {r.text}")
        self.assertEqual(self._count(models.WhatsAppMessage), 0)

    def test_unsupported_field_is_safe(self):
        r = self._post(fx.unsupported_field_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "ignored")
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 1)

    def test_unsupported_object_is_safe(self):
        r = self._post(fx.unsupported_object_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 1)
        self.assertEqual(self._count(models.WhatsAppMessage), 0)

    def test_context_reply_is_stored(self):
        self._post(fx.text_message_event(context_id="wamid.TEST_CONTEXT_001"))
        mensaje = self._first(models.WhatsAppMessage)
        self.assertEqual(mensaje.context_external_message_id, "wamid.TEST_CONTEXT_001")

    def test_closed_conversation_is_reopened_by_inbound(self):
        self._post(fx.text_message_event(message_id=fx.TEST_MESSAGE_ID))
        db = self._session()
        try:
            conversacion = db.query(models.WhatsAppConversation).one()
            conversacion.status = "closed"
            db.commit()
        finally:
            db.close()
        self._post(fx.text_message_event(message_id=fx.TEST_MESSAGE_ID_2))
        # unique(line_id, contact_id) => se reabre el mismo hilo, no se crea otro.
        self.assertEqual(self._count(models.WhatsAppConversation), 1)
        self.assertEqual(self._first(models.WhatsAppConversation).status, "open")

    def test_logs_do_not_leak_personal_data(self):
        secreto = "texto-confidencial-del-cliente"
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured:
            self._post(fx.text_message_event(body=secreto))
        joined = "\n".join(captured.output)
        self.assertNotIn(secreto, joined)
        self.assertNotIn(fx.TEST_WA_ID, joined)
        self.assertNotIn(fx.TEST_PROFILE_NAME, joined)
        self.assertNotIn(fx.TEST_APP_SECRET, joined)
        self.assertNotIn(fx.TEST_MESSAGE_ID, joined)


# =============================================================================== #
# POST — resolución de línea
# =============================================================================== #
class WebhookLineResolutionTest(WebhookTestBase):
    def test_unknown_line_is_not_auto_created(self):
        r = self._post(fx.text_message_event(phone_number_id="TEST_PHONE_NUMBER_ID_DESCONOCIDO"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppLine), 0)
        self.assertEqual(self._count(models.WhatsAppMessage), 0)
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.processing_status, "ignored")
        self.assertIn("unknown_line", evento.last_error_safe)

    def test_unknown_line_keeps_traceability(self):
        self._post(fx.text_message_event(phone_number_id="TEST_OTRO_ID"))
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertIsNotNone(evento.raw_payload)
        self.assertIsNotNone(evento.payload_hash)

    def test_inactive_line_does_not_process_but_keeps_event(self):
        self._seed_line(is_active=False)
        r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppMessage), 0)
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.processing_status, "ignored")
        self.assertIn("inactive_line", evento.last_error_safe)

    def test_line_of_another_phone_number_id_is_not_matched(self):
        self._seed_line(phone_number_id=fx.TEST_PHONE_NUMBER_ID_B,
                        display_number=fx.TEST_DISPLAY_NUMBER_B)
        self._post(fx.text_message_event(phone_number_id=fx.TEST_PHONE_NUMBER_ID))
        self.assertEqual(self._count(models.WhatsAppMessage), 0)

    def test_unknown_line_never_logs_the_full_phone_number_id(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured:
            self._post(fx.text_message_event(phone_number_id="TEST_PHONE_NUMBER_ID_SECRETO"))
        self.assertNotIn("TEST_PHONE_NUMBER_ID_SECRETO", "\n".join(captured.output))


# =============================================================================== #
# POST — estados de mensajes
# =============================================================================== #
class WebhookStatusTest(WebhookTestBase):
    def setUp(self):
        super().setUp()
        self.line_id = self._seed_line()
        self.message_id = self._seed_outbound_message(self.line_id)

    def _message(self):
        db = self._session()
        try:
            return db.query(models.WhatsAppMessage).filter(
                models.WhatsAppMessage.id == self.message_id).one()
        finally:
            db.close()

    def test_sent_status(self):
        r = self._post(fx.status_event(status="sent"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 1)
        self.assertEqual(self._message().current_status, "sent")

    def test_delivered_status(self):
        self._post(fx.status_event(status="sent", timestamp="1700000001"))
        self._post(fx.status_event(status="delivered", timestamp="1700000002"))
        self.assertEqual(self._message().current_status, "delivered")
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 2)

    def test_read_status(self):
        self._post(fx.status_event(status="sent", timestamp="1700000001"))
        self._post(fx.status_event(status="delivered", timestamp="1700000002"))
        self._post(fx.status_event(status="read", timestamp="1700000003"))
        self.assertEqual(self._message().current_status, "read")
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 3)

    def test_failed_status_stores_sanitized_error(self):
        r = self._post(fx.failed_status_event())
        self.assertEqual(r.status_code, 200, r.text)
        mensaje = self._message()
        self.assertEqual(mensaje.current_status, "failed")
        self.assertEqual(mensaje.error_code, "131047")
        self.assertEqual(mensaje.error_message_safe, "Re-engagement message")
        evento = self._first(models.WhatsAppMessageStatusEvent)
        # El payload guardado es sanitizado: sin teléfono completo.
        self.assertNotIn(fx.TEST_WA_ID, json.dumps(evento.safe_payload))

    def test_repeated_status_does_not_duplicate(self):
        payload = fx.status_event(status="delivered", timestamp="1700000002")
        self._post(payload)
        r = self._post(payload)
        self.assertTrue(r.json()["duplicate"])
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 1)

    def test_same_status_in_a_different_event_does_not_duplicate(self):
        self._post(fx.status_event(status="delivered", timestamp="1700000002"))
        # Mismo estado y timestamp dentro de otro webhook (event_key distinto).
        payload = fx.status_event(status="delivered", timestamp="1700000002")
        payload["entry"][0]["time"] = 12345
        r = self._post(payload)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["duplicate"])
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 1)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 2)

    def test_out_of_order_statuses_do_not_regress(self):
        self._post(fx.status_event(status="read", timestamp="1700000003"))
        self._post(fx.status_event(status="delivered", timestamp="1700000002"))
        self._post(fx.status_event(status="sent", timestamp="1700000001"))
        self.assertEqual(self._message().current_status, "read")
        # El historial se conserva completo aunque el estado actual no cambie.
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 3)

    def test_failed_after_delivered_keeps_delivery_proof(self):
        self._post(fx.status_event(status="delivered", timestamp="1700000002"))
        self._post(fx.failed_status_event(timestamp="1700000004"))
        self.assertEqual(self._message().current_status, "delivered")
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 2)

    def test_status_for_unknown_message_is_ignored(self):
        r = self._post(fx.status_event(message_id=fx.TEST_UNKNOWN_MESSAGE_ID, status="read"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "ignored")
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 0)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertIn("unknown_external_message", evento.last_error_safe)

    def test_unsupported_status_is_ignored(self):
        r = self._post(fx.status_event(status="deleted"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppMessageStatusEvent), 0)

    def test_history_is_append_only(self):
        for i, estado in enumerate(["sent", "delivered", "read"], start=1):
            self._post(fx.status_event(status=estado, timestamp=f"170000000{i}"))
        db = self._session()
        try:
            eventos = db.query(models.WhatsAppMessageStatusEvent).all()
            self.assertEqual({e.status for e in eventos}, {"sent", "delivered", "read"})
            self.assertEqual(len({e.event_key for e in eventos}), 3)
        finally:
            db.close()

    def test_status_logs_do_not_leak_recipient(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured:
            self._post(fx.status_event(status="read"))
        self.assertNotIn(fx.TEST_WA_ID, "\n".join(captured.output))


# =============================================================================== #
# POST — estrategia transaccional
# =============================================================================== #
class WebhookTransactionTest(WebhookTestBase):
    def setUp(self):
        super().setUp()
        self.line_id = self._seed_line()

    def test_failure_persisting_event_returns_500(self):
        with mock.patch.object(wa_events, "persist_event", side_effect=RuntimeError("db caída")):
            r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 0)

    def test_error_resolving_contact_keeps_event_and_returns_200(self):
        with mock.patch.object(wa_processor, "_resolve_contact",
                               side_effect=RuntimeError("fallo de contacto")):
            r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "failed")
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        self.assertEqual(self._count(models.WhatsAppMessage), 0)
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.processing_status, "failed")
        self.assertEqual(evento.attempt_count, 1)
        self.assertIn("fallo de contacto", evento.last_error_safe)
        self.assertIsNotNone(evento.raw_payload)

    def test_error_resolving_conversation_rolls_back_the_contact(self):
        with mock.patch.object(wa_processor, "_resolve_conversation",
                               side_effect=RuntimeError("fallo de conversación")):
            r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)
        # El contacto se había creado en la MISMA transacción: debe quedar revertido.
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        self.assertEqual(self._count(models.WhatsAppContactIdentifier), 0)
        self.assertEqual(self._count(models.WhatsAppConversation), 0)
        self.assertEqual(self._first(models.WhatsAppWebhookEvent).processing_status, "failed")

    def test_error_persisting_message_rolls_back_contact_and_conversation(self):
        # Conversación inexistente => la FK del mensaje falla al confirmar.
        fantasma = types.SimpleNamespace(id=999999)
        with mock.patch.object(wa_processor, "_resolve_conversation", return_value=fantasma):
            r = self._post(fx.text_message_event())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "failed")
        self.assertEqual(self._count(models.WhatsAppMessage), 0)
        self.assertEqual(self._count(models.WhatsAppContact), 0)
        self.assertEqual(self._count(models.WhatsAppContactIdentifier), 0)
        self.assertEqual(self._first(models.WhatsAppWebhookEvent).processing_status, "failed")

    def test_one_failing_item_does_not_block_the_others(self):
        """Dos mensajes en un mismo webhook: si el primero falla, el segundo se procesa."""
        payload = fx.text_message_event()
        mensajes = payload["entry"][0]["changes"][0]["value"]["messages"]
        roto = dict(mensajes[0])
        roto["id"] = None  # sin id externo => no soportado, se descarta sin romper
        mensajes.insert(0, roto)

        r = self._post(payload)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._count(models.WhatsAppMessage), 1)
        self.assertEqual(self._first(models.WhatsAppMessage).external_message_id,
                         fx.TEST_MESSAGE_ID)

    def test_error_is_sanitized_before_persisting(self):
        secreto = "texto-confidencial-del-cliente"
        with mock.patch.object(wa_processor, "_resolve_contact",
                               side_effect=RuntimeError("x" * 500)):
            self._post(fx.text_message_event(body=secreto))
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertLessEqual(len(evento.last_error_safe), 200)
        self.assertNotIn(secreto, evento.last_error_safe)
        self.assertNotIn("\n", evento.last_error_safe)

    def test_event_is_retriable_after_failure(self):
        """El evento fallido queda con su payload crudo para reproceso posterior."""
        with mock.patch.object(wa_processor, "_resolve_contact",
                               side_effect=RuntimeError("fallo transitorio")):
            self._post(fx.text_message_event())
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.processing_status, "failed")
        self.assertIsNotNone(evento.raw_payload)
        self.assertGreaterEqual(evento.attempt_count, 1)

        # El reintento de Meta del mismo payload NO reprocesa (dedupe por event_key):
        # el reproceso es responsabilidad del procesador persistente (etapa siguiente).
        r = self._post(fx.text_message_event())
        self.assertTrue(r.json()["duplicate"])
        self.assertEqual(self._count(models.WhatsAppWebhookEvent), 1)


# =============================================================================== #
# Persistencia del evento: retención y contenido
# =============================================================================== #
class WebhookEventPersistenceTest(WebhookTestBase):
    def setUp(self):
        super().setUp()
        self.line_id = self._seed_line()

    def test_raw_payload_has_bounded_retention(self):
        self._post(fx.text_message_event())
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertIsNotNone(evento.raw_payload_expires_at)
        esperado = datetime.now(timezone.utc) + timedelta(days=wa_config.RAW_PAYLOAD_RETENTION_DAYS)
        vence = evento.raw_payload_expires_at
        if vence.tzinfo is None:  # SQLite devuelve naive
            vence = vence.replace(tzinfo=timezone.utc)
        self.assertLess(abs((vence - esperado).total_seconds()), 120)

    def test_event_never_stores_secrets(self):
        self._post(fx.text_message_event())
        evento = self._first(models.WhatsAppWebhookEvent)
        serializado = json.dumps(evento.raw_payload)
        self.assertNotIn(fx.TEST_APP_SECRET, serializado)
        self.assertNotIn(fx.TEST_VERIFY_TOKEN, serializado)
        columnas = set(models.WhatsAppWebhookEvent.__table__.columns.keys())
        self.assertEqual(columnas & {"app_secret", "verify_token", "access_token"}, set())

    def test_payload_hash_matches_event_key(self):
        self._post(fx.text_message_event())
        evento = self._first(models.WhatsAppWebhookEvent)
        self.assertEqual(evento.event_key, f"sha256:{evento.payload_hash}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""
Tests del cliente real de Meta Graph API (Etapa 1I.2A) — `MetaGraphWhatsAppSender`.

Sin red: todo pasa por `httpx.MockTransport`. Cubre:
  - clasificación completa de resultados (accepted / ambiguous / definitive_failure);
  - forma exacta del request (URL, Authorization, payload de texto);
  - sin access token: fallo definitivo SIN tocar la red;
  - seguridad de logs: ni token, ni recipient, ni texto, ni phone_number_id;
  - helpers de configuración (versión de Graph API, timeouts acotados);
  - wiring de `get_whatsapp_sender` (Disabled salvo flag on + token).

Correr desde backend/:  python -m unittest tests.test_whatsapp_meta_sender -v
"""

import asyncio
import json
import os
import unittest
from unittest import mock

import httpx

from app.services.whatsapp import config as wa_config
from app.services.whatsapp.meta_sender import (
    CODE_NOT_CONFIGURED,
    CODE_PROVIDER_AUTH_ERROR,
    CODE_PROVIDER_RATE_LIMITED,
    CODE_PROVIDER_REJECTED,
    CODE_PROVIDER_RESULT_UNKNOWN,
    MetaGraphWhatsAppSender,
)
from app.services.whatsapp.outbound import CODE_ACCEPTED_NO_EXTERNAL_ID
from app.services.whatsapp.sender import (
    OUTCOME_ACCEPTED,
    OUTCOME_AMBIGUOUS,
    OUTCOME_DEFINITIVE_FAILURE,
    DisabledWhatsAppSender,
    SendTextCommand,
)
from app.routers.whatsapp_inbox import get_whatsapp_sender

# Datos 100% ficticios de test (nunca valores reales).
FAKE_TOKEN = "test-token-ficticio-no-real"
FAKE_PHONE_NUMBER_ID = "PHONE_ID_TEST_123"
FAKE_RECIPIENT = "+5490000000000"
FAKE_TEXT = "texto ficticio de prueba"
FAKE_WAMID = "wamid.TEST_FICTICIO_ABC"

COMMAND = SendTextCommand(
    internal_message_id=42,
    phone_number_id=FAKE_PHONE_NUMBER_ID,
    recipient=FAKE_RECIPIENT,
    text=FAKE_TEXT,
)

TOKEN_ENV = {wa_config.OUTBOUND_ACCESS_TOKEN_ENV: FAKE_TOKEN}


def _send(handler) -> tuple:
    """Ejecuta un envío con MockTransport y devuelve (result, requests_capturados)."""
    captured = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    sender = MetaGraphWhatsAppSender(transport=httpx.MockTransport(_handler))
    result = asyncio.run(sender.send_text(COMMAND))
    return result, captured


def _json_response(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body)


class MetaSenderClassificationTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, TOKEN_ENV, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------ accepted ---------------------------------
    def test_2xx_with_wamid_is_accepted(self):
        result, _ = _send(lambda r: _json_response(200, {"messages": [{"id": FAKE_WAMID}]}))
        self.assertEqual(result.outcome, OUTCOME_ACCEPTED)
        self.assertEqual(result.external_message_id, FAKE_WAMID)
        self.assertEqual(result.http_status, 200)

    def test_wamid_is_stripped(self):
        result, _ = _send(lambda r: _json_response(201, {"messages": [{"id": f"  {FAKE_WAMID}  "}]}))
        self.assertEqual(result.outcome, OUTCOME_ACCEPTED)
        self.assertEqual(result.external_message_id, FAKE_WAMID)

    # ----------------------- 2xx sin wamid -> ambiguous ----------------------
    def test_2xx_without_messages_is_ambiguous(self):
        result, _ = _send(lambda r: _json_response(200, {"messaging_product": "whatsapp"}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_ACCEPTED_NO_EXTERNAL_ID)
        self.assertIsNone(result.external_message_id)

    def test_2xx_with_empty_wamid_is_ambiguous(self):
        result, _ = _send(lambda r: _json_response(200, {"messages": [{"id": "   "}]}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_ACCEPTED_NO_EXTERNAL_ID)

    def test_2xx_with_non_json_body_is_ambiguous(self):
        result, _ = _send(lambda r: httpx.Response(200, content=b"<html>not json</html>"))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_ACCEPTED_NO_EXTERNAL_ID)

    # -------------------------- fallos definitivos ---------------------------
    def test_400_is_definitive_rejected(self):
        result, _ = _send(lambda r: _json_response(400, {"error": {"message": "bad"}}))
        self.assertEqual(result.outcome, OUTCOME_DEFINITIVE_FAILURE)
        self.assertEqual(result.error_code, CODE_PROVIDER_REJECTED)
        self.assertEqual(result.http_status, 400)

    def test_404_is_definitive_rejected(self):
        result, _ = _send(lambda r: _json_response(404, {"error": {}}))
        self.assertEqual(result.outcome, OUTCOME_DEFINITIVE_FAILURE)
        self.assertEqual(result.error_code, CODE_PROVIDER_REJECTED)

    def test_401_is_definitive_auth(self):
        result, _ = _send(lambda r: _json_response(401, {"error": {}}))
        self.assertEqual(result.outcome, OUTCOME_DEFINITIVE_FAILURE)
        self.assertEqual(result.error_code, CODE_PROVIDER_AUTH_ERROR)

    def test_403_is_definitive_auth(self):
        result, _ = _send(lambda r: _json_response(403, {"error": {}}))
        self.assertEqual(result.outcome, OUTCOME_DEFINITIVE_FAILURE)
        self.assertEqual(result.error_code, CODE_PROVIDER_AUTH_ERROR)

    # ------------------------------ ambiguos ---------------------------------
    def test_429_is_ambiguous_rate_limited(self):
        result, _ = _send(lambda r: _json_response(429, {"error": {}}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RATE_LIMITED)

    def test_500_is_ambiguous(self):
        result, _ = _send(lambda r: _json_response(500, {"error": {}}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RESULT_UNKNOWN)

    def test_503_is_ambiguous(self):
        result, _ = _send(lambda r: _json_response(503, {}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RESULT_UNKNOWN)

    def test_unrecognized_4xx_is_ambiguous(self):
        # Solo lo CLARAMENTE definitivo es definitivo; un 422 raro queda ambiguo.
        result, _ = _send(lambda r: _json_response(422, {}))
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RESULT_UNKNOWN)

    def test_timeout_is_ambiguous(self):
        def _raise(request):
            raise httpx.ConnectTimeout("boom", request=request)
        result, _ = _send(_raise)
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RESULT_UNKNOWN)

    def test_disconnect_is_ambiguous(self):
        def _raise(request):
            raise httpx.RemoteProtocolError("closed", request=request)
        result, _ = _send(_raise)
        self.assertEqual(result.outcome, OUTCOME_AMBIGUOUS)
        self.assertEqual(result.error_code, CODE_PROVIDER_RESULT_UNKNOWN)


class MetaSenderRequestShapeTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, TOKEN_ENV, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_request_url_headers_and_payload(self):
        result, captured = _send(lambda r: _json_response(200, {"messages": [{"id": FAKE_WAMID}]}))
        self.assertEqual(result.outcome, OUTCOME_ACCEPTED)
        self.assertEqual(len(captured), 1)
        request = captured[0]

        version = wa_config.get_graph_api_version()
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.host, "graph.facebook.com")
        self.assertEqual(request.url.path, f"/{version}/{FAKE_PHONE_NUMBER_ID}/messages")
        self.assertEqual(request.headers.get("Authorization"), f"Bearer {FAKE_TOKEN}")

        body = json.loads(request.content.decode("utf-8"))
        self.assertEqual(body, {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": FAKE_RECIPIENT,
            "type": "text",
            "text": {"preview_url": False, "body": FAKE_TEXT},
        })

    def test_graph_api_version_override_reaches_url(self):
        with mock.patch.dict(os.environ, {wa_config.GRAPH_API_VERSION_ENV: "v21.0"}, clear=False):
            _, captured = _send(lambda r: _json_response(200, {"messages": [{"id": FAKE_WAMID}]}))
        self.assertTrue(captured[0].url.path.startswith("/v21.0/"))


class MetaSenderNoTokenTest(unittest.TestCase):
    def test_without_token_no_network_and_definitive_failure(self):
        called = []

        def _handler(request):
            called.append(request)
            return _json_response(200, {"messages": [{"id": FAKE_WAMID}]})

        env_sin_token = {wa_config.OUTBOUND_ACCESS_TOKEN_ENV: ""}
        with mock.patch.dict(os.environ, env_sin_token, clear=False):
            sender = MetaGraphWhatsAppSender(transport=httpx.MockTransport(_handler))
            result = asyncio.run(sender.send_text(COMMAND))

        self.assertEqual(result.outcome, OUTCOME_DEFINITIVE_FAILURE)
        self.assertEqual(result.error_code, CODE_NOT_CONFIGURED)
        self.assertEqual(called, [], "sin token NO debe tocarse la red")


class MetaSenderLogSafetyTest(unittest.TestCase):
    """Ningún log del sender puede contener token, recipient, texto ni phone_number_id."""

    SECRETS = (FAKE_TOKEN, FAKE_RECIPIENT, FAKE_TEXT, FAKE_PHONE_NUMBER_ID, FAKE_WAMID)

    def _assert_logs_clean(self, handler):
        with mock.patch.dict(os.environ, TOKEN_ENV, clear=False):
            with self.assertLogs("uvicorn.error", level="INFO") as captured:
                _send(handler)
        for line in captured.output:
            for secret in self.SECRETS:
                self.assertNotIn(secret, line, f"log filtra dato sensible: {secret[:8]}...")

    def test_logs_clean_on_accepted(self):
        self._assert_logs_clean(lambda r: _json_response(200, {"messages": [{"id": FAKE_WAMID}]}))

    def test_logs_clean_on_definitive_failure(self):
        self._assert_logs_clean(lambda r: _json_response(401, {"error": {"message": FAKE_RECIPIENT}}))

    def test_logs_clean_on_exception(self):
        def _raise(request):
            # El mensaje de la excepción contiene datos sensibles a propósito:
            # el sender solo debe loguear el TIPO, nunca el detalle.
            raise httpx.ConnectError(f"fallo hacia {FAKE_RECIPIENT} con {FAKE_TOKEN}", request=request)
        self._assert_logs_clean(_raise)


class ConfigHelpersTest(unittest.TestCase):
    def test_version_default(self):
        with mock.patch.dict(os.environ, {wa_config.GRAPH_API_VERSION_ENV: ""}, clear=False):
            self.assertEqual(wa_config.get_graph_api_version(), wa_config.DEFAULT_GRAPH_API_VERSION)

    def test_version_malformed_falls_back(self):
        for bad in ("20.0", "vabc", "v", "https://x"):
            with mock.patch.dict(os.environ, {wa_config.GRAPH_API_VERSION_ENV: bad}, clear=False):
                self.assertEqual(wa_config.get_graph_api_version(), wa_config.DEFAULT_GRAPH_API_VERSION)

    def test_version_valid_override(self):
        with mock.patch.dict(os.environ, {wa_config.GRAPH_API_VERSION_ENV: "v21.0"}, clear=False):
            self.assertEqual(wa_config.get_graph_api_version(), "v21.0")

    def test_timeouts_default_and_bounds(self):
        with mock.patch.dict(os.environ, {wa_config.CONNECT_TIMEOUT_ENV: "", wa_config.READ_TIMEOUT_ENV: "abc"}, clear=False):
            self.assertEqual(wa_config.get_connect_timeout_seconds(), wa_config.DEFAULT_CONNECT_TIMEOUT_SECONDS)
            self.assertEqual(wa_config.get_read_timeout_seconds(), wa_config.DEFAULT_READ_TIMEOUT_SECONDS)
        with mock.patch.dict(os.environ, {wa_config.CONNECT_TIMEOUT_ENV: "0.001", wa_config.READ_TIMEOUT_ENV: "9999"}, clear=False):
            self.assertEqual(wa_config.get_connect_timeout_seconds(), wa_config.MIN_TIMEOUT_SECONDS)
            self.assertEqual(wa_config.get_read_timeout_seconds(), wa_config.MAX_TIMEOUT_SECONDS)

    def test_sender_configured(self):
        with mock.patch.dict(os.environ, {wa_config.OUTBOUND_ACCESS_TOKEN_ENV: ""}, clear=False):
            self.assertFalse(wa_config.outbound_sender_configured())
        with mock.patch.dict(os.environ, TOKEN_ENV, clear=False):
            self.assertTrue(wa_config.outbound_sender_configured())


class SenderWiringTest(unittest.TestCase):
    """`get_whatsapp_sender`: MetaGraph SOLO con flag encendido Y token presente."""

    def test_disabled_when_flag_off(self):
        with mock.patch.dict(os.environ, {wa_config.OUTBOUND_ENABLED_ENV: "", **TOKEN_ENV}, clear=False):
            self.assertIsInstance(get_whatsapp_sender(), DisabledWhatsAppSender)

    def test_disabled_when_flag_on_but_no_token(self):
        env = {wa_config.OUTBOUND_ENABLED_ENV: "true", wa_config.OUTBOUND_ACCESS_TOKEN_ENV: ""}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertIsInstance(get_whatsapp_sender(), DisabledWhatsAppSender)

    def test_meta_when_flag_on_and_token(self):
        env = {wa_config.OUTBOUND_ENABLED_ENV: "true", **TOKEN_ENV}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertIsInstance(get_whatsapp_sender(), MetaGraphWhatsAppSender)


if __name__ == "__main__":
    unittest.main(verbosity=2)

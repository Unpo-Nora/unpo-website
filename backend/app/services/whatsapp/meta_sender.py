"""
Cliente real de Meta Graph API para el envío saliente de texto (Etapa 1I.2A).

Implementa el Protocol `WhatsAppSender` con `httpx.AsyncClient` contra:

    POST https://graph.facebook.com/{version}/{phone_number_id}/messages

Clasificación de resultados (contrato 1I.2A — NUNCA auto-retry):

    2xx con `messages[0].id`             -> accepted   (external_message_id = wamid)
    2xx sin wamid (o body no parseable)  -> ambiguous  WHATSAPP_ACCEPTED_WITHOUT_EXTERNAL_ID
    timeout / desconexión / error httpx  -> ambiguous  WHATSAPP_PROVIDER_RESULT_UNKNOWN
    429                                  -> ambiguous  WHATSAPP_PROVIDER_RATE_LIMITED
    5xx y estados no reconocidos         -> ambiguous  WHATSAPP_PROVIDER_RESULT_UNKNOWN
    401 / 403 (auth/config)              -> definitive WHATSAPP_PROVIDER_AUTH_ERROR
    400 / 404 (payload/config inválidos) -> definitive WHATSAPP_PROVIDER_REJECTED
    sin access token configurado         -> definitive WHATSAPP_SENDER_NOT_CONFIGURED
                                            (sin tocar la red)

Seguridad de logs (mismo estándar que el hardening 1I.1B): SOLO se loguean
`internal_message_id`, outcome, HTTP status de Meta, `error_code` estable,
duración y tipo de excepción. JAMÁS: access token, recipient, texto, payload,
respuesta cruda de Meta, `phone_number_id` ni la URL completa.

El flag `WHATSAPP_OUTBOUND_ENABLED` sigue gobernando el endpoint (503 con flag
apagado, antes de crear filas); este cliente solo se instala en runtime cuando el
flag está encendido Y hay token configurado (ver `get_whatsapp_sender`).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from . import config as wa_config
from .outbound import CODE_ACCEPTED_NO_EXTERNAL_ID
from .sender import (
    OUTCOME_ACCEPTED,
    OUTCOME_AMBIGUOUS,
    OUTCOME_DEFINITIVE_FAILURE,
    SendResult,
    SendTextCommand,
)

logger = logging.getLogger("uvicorn.error")

GRAPH_BASE_URL = "https://graph.facebook.com"

# Códigos estables propios del cliente (los de contrato general viven en outbound.py).
CODE_PROVIDER_RESULT_UNKNOWN = "WHATSAPP_PROVIDER_RESULT_UNKNOWN"
CODE_PROVIDER_RATE_LIMITED = "WHATSAPP_PROVIDER_RATE_LIMITED"
CODE_PROVIDER_AUTH_ERROR = "WHATSAPP_PROVIDER_AUTH_ERROR"
CODE_PROVIDER_REJECTED = "WHATSAPP_PROVIDER_REJECTED"
CODE_NOT_CONFIGURED = "WHATSAPP_SENDER_NOT_CONFIGURED"

# Clasificación por HTTP status (todo lo no listado y no-2xx es ambiguo por diseño:
# solo lo CLARAMENTE definitivo se marca definitivo; unknown nunca se reenvía solo).
_DEFINITIVE_AUTH_STATUSES = frozenset({401, 403})
_DEFINITIVE_REJECTED_STATUSES = frozenset({400, 404})


def _extract_wamid(response: httpx.Response) -> Optional[str]:
    """`messages[0].id` del body 2xx de Meta, o None si falta/está vacío/no parsea."""
    try:
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    if not isinstance(first, dict):
        return None
    raw = first.get("id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


class MetaGraphWhatsAppSender:
    """
    Sender real contra Meta Graph API. Sin reintentos: cada invocación es UN intento;
    la ambigüedad la resuelve el webhook de statuses o el reconciliador (1I.2B).

    `transport` permite inyectar `httpx.MockTransport` en tests; en runtime queda None
    y httpx usa el transporte HTTP real.
    """

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._transport = transport

    def _log(self, command: SendTextCommand, outcome: str, *, http_status: Optional[int] = None,
             error_code: Optional[str] = None, duration_ms: Optional[int] = None,
             exception_type: Optional[str] = None) -> None:
        # SOLO metadatos seguros (ver docstring del módulo).
        logger.info(
            "whatsapp outbound sender: message_id=%s outcome=%s http_status=%s error_code=%s duration_ms=%s exception_type=%s",
            command.internal_message_id, outcome, http_status, error_code, duration_ms, exception_type,
        )

    async def send_text(self, command: SendTextCommand) -> SendResult:
        token = wa_config.get_outbound_access_token()
        if not token:
            # Defensa en profundidad: el wiring no debería instalar este sender sin token.
            # Sin token NO se toca la red: fallo definitivo controlado.
            self._log(command, OUTCOME_DEFINITIVE_FAILURE, error_code=CODE_NOT_CONFIGURED)
            return SendResult(
                outcome=OUTCOME_DEFINITIVE_FAILURE,
                error_code=CODE_NOT_CONFIGURED,
                error_message_safe="outbound sender not configured",
            )

        version = wa_config.get_graph_api_version()
        url = f"{GRAPH_BASE_URL}/{version}/{command.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": command.recipient,
            "type": "text",
            "text": {"preview_url": False, "body": command.text},
        }
        connect_t = wa_config.get_connect_timeout_seconds()
        read_t = wa_config.get_read_timeout_seconds()
        timeout = httpx.Timeout(connect=connect_t, read=read_t, write=read_t, pool=connect_t)

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.post(
                    url, json=payload, headers={"Authorization": f"Bearer {token}"}
                )
        except Exception as exc:
            # Timeout, desconexión o cualquier fallo de transporte: no sabemos si Meta
            # recibió el mensaje -> ambiguo. Solo se loguea el TIPO de excepción.
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log(command, OUTCOME_AMBIGUOUS, error_code=CODE_PROVIDER_RESULT_UNKNOWN,
                      duration_ms=duration_ms, exception_type=type(exc).__name__)
            return SendResult(
                outcome=OUTCOME_AMBIGUOUS,
                error_code=CODE_PROVIDER_RESULT_UNKNOWN,
                error_message_safe="provider result unknown",
            )

        duration_ms = int((time.monotonic() - started) * 1000)
        status = response.status_code

        if 200 <= status < 300:
            wamid = _extract_wamid(response)
            if wamid:
                self._log(command, OUTCOME_ACCEPTED, http_status=status, duration_ms=duration_ms)
                return SendResult(
                    outcome=OUTCOME_ACCEPTED,
                    external_message_id=wamid,
                    http_status=status,
                )
            # 2xx sin wamid: Meta pudo haberlo tomado igual -> ambiguo, nunca accepted.
            self._log(command, OUTCOME_AMBIGUOUS, http_status=status,
                      error_code=CODE_ACCEPTED_NO_EXTERNAL_ID, duration_ms=duration_ms)
            return SendResult(
                outcome=OUTCOME_AMBIGUOUS,
                http_status=status,
                error_code=CODE_ACCEPTED_NO_EXTERNAL_ID,
                error_message_safe="provider accepted without message id",
            )

        if status in _DEFINITIVE_AUTH_STATUSES:
            self._log(command, OUTCOME_DEFINITIVE_FAILURE, http_status=status,
                      error_code=CODE_PROVIDER_AUTH_ERROR, duration_ms=duration_ms)
            return SendResult(
                outcome=OUTCOME_DEFINITIVE_FAILURE,
                http_status=status,
                error_code=CODE_PROVIDER_AUTH_ERROR,
                error_message_safe="provider auth/config error",
            )

        if status in _DEFINITIVE_REJECTED_STATUSES:
            self._log(command, OUTCOME_DEFINITIVE_FAILURE, http_status=status,
                      error_code=CODE_PROVIDER_REJECTED, duration_ms=duration_ms)
            return SendResult(
                outcome=OUTCOME_DEFINITIVE_FAILURE,
                http_status=status,
                error_code=CODE_PROVIDER_REJECTED,
                error_message_safe="provider rejected the request",
            )

        if status == 429:
            self._log(command, OUTCOME_AMBIGUOUS, http_status=status,
                      error_code=CODE_PROVIDER_RATE_LIMITED, duration_ms=duration_ms)
            return SendResult(
                outcome=OUTCOME_AMBIGUOUS,
                http_status=status,
                error_code=CODE_PROVIDER_RATE_LIMITED,
                error_message_safe="rate limited by provider",
            )

        # 5xx y cualquier estado no reconocido: ambiguo por diseño.
        self._log(command, OUTCOME_AMBIGUOUS, http_status=status,
                  error_code=CODE_PROVIDER_RESULT_UNKNOWN, duration_ms=duration_ms)
        return SendResult(
            outcome=OUTCOME_AMBIGUOUS,
            http_status=status,
            error_code=CODE_PROVIDER_RESULT_UNKNOWN,
            error_message_safe="provider result unknown",
        )

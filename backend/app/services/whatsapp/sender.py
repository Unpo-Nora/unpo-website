"""
Abstracción de envío saliente de WhatsApp (Etapa 1I.1).

1I.1 **no habla con Meta**: define únicamente el CONTRATO del sender y una implementación
`DisabledWhatsAppSender` que NO realiza red. El cliente real (httpx + Graph API) llega en
1I.2. Los tests inyectan un `FakeWhatsAppSender` que vive en `tests/`, nunca en runtime.

Deliberadamente NO se importa `httpx`, `requests` ni `graph.facebook.com` en este archivo:
esta etapa debe tener CERO llamadas HTTP externas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

# Resultado de un intento de envío (sin exponer NADA crudo de Meta).
OUTCOME_ACCEPTED = "accepted"                 # Meta aceptó; hay wamid.
OUTCOME_DEFINITIVE_FAILURE = "definitive_failure"  # rechazo definitivo (4xx, auth, etc.).
OUTCOME_AMBIGUOUS = "ambiguous"               # timeout/5xx/desconexión: no se sabe el resultado.

VALID_OUTCOMES = frozenset({OUTCOME_ACCEPTED, OUTCOME_DEFINITIVE_FAILURE, OUTCOME_AMBIGUOUS})


@dataclass(frozen=True)
class SendTextCommand:
    """Orden de envío de un texto. Contiene datos sensibles (recipient, phone_number_id)
    que se pasan al sender pero NUNCA se exponen en respuestas ni logs."""
    internal_message_id: int
    phone_number_id: str
    recipient: str
    text: str


@dataclass(frozen=True)
class SendResult:
    """Resultado normalizado del sender. `error_message_safe` ya viene redactado; el
    servicio vuelve a pasarlo por `safe_error` por las dudas antes de persistir."""
    outcome: str
    external_message_id: Optional[str] = None
    provider_status: Optional[str] = None
    http_status: Optional[int] = None
    error_code: Optional[str] = None
    error_message_safe: Optional[str] = None


@runtime_checkable
class WhatsAppSender(Protocol):
    """Contrato mínimo del sender. La implementación real (1I.2) hará la llamada HTTP."""

    async def send_text(self, command: SendTextCommand) -> SendResult:  # pragma: no cover - protocolo
        ...


class DisabledWhatsAppSender:
    """
    Sender de runtime para 1I.1: **no realiza red**.

    El endpoint solo lo alcanza si el flag `WHATSAPP_OUTBOUND_ENABLED` estuviera encendido
    (default apagado ⇒ 503 antes de reservar). En 1I.1 no hay cliente real, así que ante
    una invocación devuelve un fallo definitivo controlado, sin tocar la red y sin filtrar
    nada. El mensaje reservado queda `failed` de forma segura.
    """

    async def send_text(self, command: SendTextCommand) -> SendResult:
        return SendResult(
            outcome=OUTCOME_DEFINITIVE_FAILURE,
            error_code="WHATSAPP_SENDER_DISABLED",
            error_message_safe="outbound sender not configured",
        )

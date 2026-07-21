"""
Payloads ficticios de WhatsApp Cloud API para los tests del webhook.

TODOS los datos son claramente NO productivos: ningún número real de UNPO o NORA,
ningún dato personal, ningún secreto. Los identificadores usan el prefijo TEST_ y los
teléfonos son rangos de ejemplo terminados en ceros.
"""

# --- Identificadores ficticios ------------------------------------------------
TEST_PHONE_NUMBER_ID = "TEST_PHONE_NUMBER_ID"
TEST_PHONE_NUMBER_ID_B = "TEST_PHONE_NUMBER_ID_B"
TEST_WABA_ID = "TEST_WABA_ID"
TEST_DISPLAY_NUMBER = "+540000000000"
TEST_DISPLAY_NUMBER_B = "+540000000001"

TEST_WA_ID = "5491100000000"
TEST_WA_ID_OTHER = "5491100000009"
TEST_PROFILE_NAME = "Contacto Ficticio"

TEST_MESSAGE_ID = "wamid.TEST_MESSAGE_001"
TEST_MESSAGE_ID_2 = "wamid.TEST_MESSAGE_002"
TEST_OUTBOUND_MESSAGE_ID = "wamid.TEST_OUTBOUND_001"
TEST_UNKNOWN_MESSAGE_ID = "wamid.TEST_UNKNOWN_999"

TEST_TIMESTAMP = "1700000000"
TEST_ENTRY_ID = "TEST_ENTRY_ID"

# Secretos ficticios usados solo por los tests (jamás valores con forma de credencial real).
TEST_VERIFY_TOKEN = "test-verify-token-1c"
TEST_APP_SECRET = "test-app-secret-1c"


def _envelope(changes, entry_id=TEST_ENTRY_ID, entry_time=0, obj="whatsapp_business_account"):
    return {
        "object": obj,
        "entry": [{"id": entry_id, "time": entry_time, "changes": changes}],
    }


def _metadata(phone_number_id, display_number=TEST_DISPLAY_NUMBER):
    return {"display_phone_number": display_number, "phone_number_id": phone_number_id}


def text_message_event(
    *,
    phone_number_id=TEST_PHONE_NUMBER_ID,
    wa_id=TEST_WA_ID,
    message_id=TEST_MESSAGE_ID,
    body="Hola, consulta de prueba",
    timestamp=TEST_TIMESTAMP,
    profile_name=TEST_PROFILE_NAME,
    context_id=None,
    entry_time=0,
):
    """Webhook con un mensaje entrante de tipo `text`."""
    message = {
        "from": wa_id,
        "id": message_id,
        "timestamp": timestamp,
        "type": "text",
        "text": {"body": body},
    }
    if context_id:
        message["context"] = {"id": context_id}
    value = {
        "messaging_product": "whatsapp",
        "metadata": _metadata(phone_number_id),
        "contacts": [{"profile": {"name": profile_name}, "wa_id": wa_id}],
        "messages": [message],
    }
    return _envelope([{"field": "messages", "value": value}], entry_time=entry_time)


def unsupported_message_event(
    *,
    phone_number_id=TEST_PHONE_NUMBER_ID,
    wa_id=TEST_WA_ID,
    message_id=TEST_MESSAGE_ID,
    message_type="image",
    timestamp=TEST_TIMESTAMP,
):
    """Webhook con un tipo de mensaje todavía no soportado (image/audio/location/…)."""
    value = {
        "messaging_product": "whatsapp",
        "metadata": _metadata(phone_number_id),
        "contacts": [{"profile": {"name": TEST_PROFILE_NAME}, "wa_id": wa_id}],
        "messages": [{
            "from": wa_id,
            "id": message_id,
            "timestamp": timestamp,
            "type": message_type,
            message_type: {"id": "TEST_MEDIA_ID", "mime_type": "image/jpeg"},
        }],
    }
    return _envelope([{"field": "messages", "value": value}])


def status_event(
    *,
    phone_number_id=TEST_PHONE_NUMBER_ID,
    message_id=TEST_OUTBOUND_MESSAGE_ID,
    status="sent",
    timestamp=TEST_TIMESTAMP,
    recipient_id=TEST_WA_ID,
    errors=None,
):
    """Webhook con un evento de estado de un mensaje saliente."""
    status_item = {
        "id": message_id,
        "status": status,
        "timestamp": timestamp,
        "recipient_id": recipient_id,
    }
    if errors:
        status_item["errors"] = errors
    value = {
        "messaging_product": "whatsapp",
        "metadata": _metadata(phone_number_id),
        "statuses": [status_item],
    }
    return _envelope([{"field": "messages", "value": value}])


def failed_status_event(**kwargs):
    """Estado `failed` con el bloque de errores tal como lo manda Meta."""
    kwargs.setdefault("errors", [{
        "code": 131047,
        "title": "Re-engagement message",
        "message": "Message failed to send",
    }])
    kwargs["status"] = "failed"
    return status_event(**kwargs)


def unsupported_field_event(*, phone_number_id=TEST_PHONE_NUMBER_ID):
    """Webhook de un `field` que esta etapa no procesa (p. ej. calidad de la línea)."""
    return _envelope([{
        "field": "message_template_status_update",
        "value": {"metadata": _metadata(phone_number_id), "event": "APPROVED"},
    }])


def unsupported_object_event():
    """Webhook de otro producto de Meta (Lead Ads usa `object: page`)."""
    return _envelope([{"field": "leadgen", "value": {}}], obj="page")

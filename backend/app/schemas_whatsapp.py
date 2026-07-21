"""
Schemas Pydantic del webhook de WhatsApp Cloud API (Meta).

Criterio (deliberadamente NO exhaustivo): se modela solo el **envelope mínimo** que
el procesador necesita — entry / changes / value / metadata / contacts / messages /
statuses — y todos los campos son opcionales con `extra="allow"`.

Motivo: Meta agrega campos y tipos de mensaje sin previo aviso. Un modelo estricto
haría fallar el webhook completo ante un campo nuevo; acá un payload desconocido se
normaliza a "sin elementos soportados" y se registra, sin romper la recepción.

Estos schemas NO son schemas de respuesta de la API interna: son el contrato de
entrada de Meta. La respuesta al webhook es un objeto mínimo sin datos personales.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# Los payloads de Meta traen campos que no modelamos: se aceptan y se ignoran.
_LENIENT = ConfigDict(extra="allow", populate_by_name=True)

# `timestamp` llega como string de segundos unix ("1717171717"), pero algunos
# entornos de prueba lo mandan como int. Se acepta cualquiera y se normaliza después.
Timestamp = Optional[Union[str, int]]


class WhatsAppProfile(BaseModel):
    """`contacts[].profile` — nombre de perfil que el usuario expone en WhatsApp."""
    model_config = _LENIENT

    name: Optional[str] = None


class WhatsAppContactPayload(BaseModel):
    """`value.contacts[]` — identidad del remitente (wa_id + perfil)."""
    model_config = _LENIENT

    wa_id: Optional[str] = None
    profile: Optional[WhatsAppProfile] = None


class WhatsAppTextPayload(BaseModel):
    """`messages[].text` — único tipo de contenido soportado en esta etapa."""
    model_config = _LENIENT

    body: Optional[str] = None


class WhatsAppContextPayload(BaseModel):
    """`messages[].context` — respuesta/cita de otro mensaje."""
    model_config = _LENIENT

    id: Optional[str] = None


class WhatsAppErrorPayload(BaseModel):
    """`statuses[].errors[]` — solo se persisten `code` y `title` (sanitizados)."""
    model_config = _LENIENT

    code: Optional[Union[str, int]] = None
    title: Optional[str] = None


class WhatsAppMessagePayload(BaseModel):
    """`value.messages[]` — mensaje entrante."""
    model_config = _LENIENT

    id: Optional[str] = None
    # `from` es palabra reservada de Python: se expone como `from_` vía alias.
    from_: Optional[str] = Field(default=None, alias="from")
    timestamp: Timestamp = None
    type: Optional[str] = None
    text: Optional[WhatsAppTextPayload] = None
    context: Optional[WhatsAppContextPayload] = None


class WhatsAppStatusPayload(BaseModel):
    """`value.statuses[]` — estado de un mensaje SALIENTE previamente enviado."""
    model_config = _LENIENT

    id: Optional[str] = None
    status: Optional[str] = None
    timestamp: Timestamp = None
    recipient_id: Optional[str] = None
    errors: Optional[List[WhatsAppErrorPayload]] = None


class WhatsAppValueMetadata(BaseModel):
    """`value.metadata` — identifica la línea destinataria del evento."""
    model_config = _LENIENT

    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class WhatsAppChangeValue(BaseModel):
    """`changes[].value` — contenedor de metadata + contacts + messages + statuses."""
    model_config = _LENIENT

    messaging_product: Optional[str] = None
    metadata: Optional[WhatsAppValueMetadata] = None
    contacts: Optional[List[WhatsAppContactPayload]] = None
    messages: Optional[List[WhatsAppMessagePayload]] = None
    statuses: Optional[List[WhatsAppStatusPayload]] = None
    # `errors` a nivel value (errores de cuenta/plataforma) se registra sin procesar.
    errors: Optional[List[Dict[str, Any]]] = None


class WhatsAppChange(BaseModel):
    """`entry[].changes[]` — el `field` soportado en esta etapa es `messages`."""
    model_config = _LENIENT

    field: Optional[str] = None
    value: Optional[WhatsAppChangeValue] = None


class WhatsAppEntry(BaseModel):
    """`entry[]` — una entrada por WABA."""
    model_config = _LENIENT

    id: Optional[str] = None
    time: Timestamp = None
    changes: Optional[List[WhatsAppChange]] = None


class WhatsAppWebhookEnvelope(BaseModel):
    """Envelope raíz. Para WhatsApp Cloud API, `object` == "whatsapp_business_account"."""
    model_config = _LENIENT

    object_: Optional[str] = Field(default=None, alias="object")
    entry: Optional[List[WhatsAppEntry]] = None

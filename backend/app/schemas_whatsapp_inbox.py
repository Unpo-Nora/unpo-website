"""
Schemas Pydantic de RESPUESTA/REQUEST del inbox multiagente de WhatsApp (Etapa 1G).

A diferencia de `schemas_whatsapp.py` (contrato de ENTRADA de Meta, lenient), estos son
schemas EXPLÍCITOS de la API interna autenticada. Nunca se retornan modelos SQLAlchemy
crudos: cada endpoint construye estos objetos para controlar exactamente qué se expone.

Reglas de exposición (arquitectura §9):
  - NUNCA se exponen: raw_payload, payload_hash, event_key, App Secret, verify token,
    access tokens, DATABASE_URL, phone_number_id/waba_id de la línea.
  - El teléfono/wa_id del contacto se expone SIEMPRE enmascarado (`mask_identifier`).
  - `assigned_user` expone id/nombre/rol del agente (staff interno), nunca su email.
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Límites de paginación y búsqueda (cotas duras contra abuso) -------------
CONVERSATIONS_DEFAULT_LIMIT = 30
CONVERSATIONS_MAX_LIMIT = 100
MESSAGES_DEFAULT_LIMIT = 50
MESSAGES_MAX_LIMIT = 100
SEARCH_MAX_LENGTH = 100
PREVIEW_MAX_LENGTH = 120


class LineOut(BaseModel):
    """Línea accesible para el usuario. NO expone phone_number_id ni waba_id."""
    id: int
    label: str
    display_number: str
    provider: str
    is_active: bool
    can_view: bool
    can_send: bool


class LineRef(BaseModel):
    """Referencia mínima de línea embebida en conversaciones."""
    id: int
    label: str
    display_number: str


class ContactOut(BaseModel):
    """Contacto con identificador ENMASCARADO (nunca el teléfono/wa_id completo)."""
    id: int
    display_name: Optional[str] = None
    phone_masked: Optional[str] = None


class AssignedUserOut(BaseModel):
    """Agente asignado. Se expone nombre y rol, NO el email."""
    id: int
    full_name: Optional[str] = None
    role: Optional[str] = None


class AssignableUserOut(BaseModel):
    """Usuario asignable (para el selector admin). Solo id/full_name/role; NUNCA email."""
    id: int
    full_name: Optional[str] = None
    role: str


class ConversationListItem(BaseModel):
    conversation_id: int
    line: LineRef
    status: str
    contact: ContactOut
    assigned_user: Optional[AssignedUserOut] = None
    last_message_at: Optional[datetime] = None
    last_message_direction: Optional[str] = None
    last_message_type: Optional[str] = None
    last_message_preview: Optional[str] = None
    unread_count: int


class ConversationListResponse(BaseModel):
    items: List[ConversationListItem]
    limit: int
    offset: int
    count: int
    has_more: bool


class ConversationDetail(BaseModel):
    conversation_id: int
    line: LineRef
    contact: ContactOut
    lead_id: Optional[int] = None
    assigned_user: Optional[AssignedUserOut] = None
    status: str
    unread_count: int
    last_message_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MessageOut(BaseModel):
    """Mensaje individual. NO expone external_message_id (wamid) ni raw_payload."""
    id: int
    conversation_id: int
    direction: str
    message_type: str
    text_body: Optional[str] = None
    current_status: str
    provider_timestamp: Optional[datetime] = None
    sender_user_id: Optional[int] = None
    created_at: Optional[datetime] = None


class MessagesResponse(BaseModel):
    items: List[MessageOut]
    limit: int
    count: int
    has_more: bool
    # Cursor pagination (keyset) — mecanismo documentado del historial.
    next_cursor: Optional[str] = None
    # `offset` se mantiene SOLO como compatibilidad explícitamente deprecada.
    offset: Optional[int] = None
    # Paginación BIDIRECCIONAL (1H): los items siempre vienen en orden ASC (created_at, id).
    # `older_cursor` deriva del PRIMER item entregado (cargar mensajes anteriores con
    # direction=backward); `newer_cursor` deriva del ÚLTIMO item (traer mensajes nuevos
    # con direction=forward). `direction` es el sentido de la consulta que produjo la página.
    older_cursor: Optional[str] = None
    newer_cursor: Optional[str] = None
    direction: str = "forward"


class ReadRequest(BaseModel):
    """Body opcional del marcado de leído."""
    model_config = ConfigDict(extra="forbid")
    last_read_message_id: Optional[int] = Field(default=None, ge=1)


class ReadResponse(BaseModel):
    conversation_id: int
    last_read_message_id: Optional[int] = None
    unread_count: int


class AssignmentRequest(BaseModel):
    """Body de asignación/reasignación. `extra=forbid` evita mass-assignment."""
    model_config = ConfigDict(extra="forbid")
    assigned_user_id: int = Field(ge=1)
    reason: Optional[str] = Field(default=None, max_length=255)


class AssignmentHistoryOut(BaseModel):
    id: int
    from_user_id: Optional[int] = None
    to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assignment_source: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    conversation_id: int
    assigned_user_id: Optional[int] = None
    changed: bool
    assignment: Optional[AssignmentHistoryOut] = None


class AssignmentHistoryResponse(BaseModel):
    items: List[AssignmentHistoryOut]


class LineUnread(BaseModel):
    line_id: int
    label: str
    unread_count: int


class UnreadCountsResponse(BaseModel):
    total_unread: int
    lines: List[LineUnread]


# --- Etapa 1I.1: envío saliente de texto -------------------------------------
class OutboundTextRequest(BaseModel):
    """
    Body del envío saliente. `client_request_id` es la ÚNICA autoridad de idempotencia
    (UUID válido; pydantic devuelve 422 si no lo es). No se usa Idempotency-Key header.

    El texto NO se acota por longitud en el schema: el servicio valida vacío/whitespace y
    el máximo de 4096 sobre la representación CANÓNICA (CRLF→LF), devolviendo códigos
    estables (`WHATSAPP_TEXT_EMPTY` / `WHATSAPP_TEXT_TOO_LONG`).
    """
    model_config = ConfigDict(extra="forbid")
    message_type: Literal["text"] = "text"
    text: str
    client_request_id: UUID


class OutboundSendResponse(BaseModel):
    """
    Respuesta SEGURA del envío. Reusa `MessageOut` (que NO expone external_message_id,
    recipient, wa_id, phone_number_id, waba_id, ni error técnico crudo).

    - `accepted`: Meta aceptó el mensaje (hay wamid).
    - `duplicate`: replay idempotente del mismo `client_request_id`.
    - `outcome`: `accepted` | `failed` | `unknown` (unknown = pending/sending/ambiguo).
    """
    message: MessageOut
    accepted: bool
    duplicate: bool
    outcome: Literal["accepted", "failed", "unknown"]

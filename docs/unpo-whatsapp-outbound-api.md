# WhatsApp — API de mensajería saliente (Etapa 1I.1)

Contrato del endpoint de envío de texto saliente. En 1I.1 el envío está **detrás de un
feature flag** (`WHATSAPP_OUTBOUND_ENABLED`, default false) y **no llama a Meta**.

## `POST /whatsapp/conversations/{conversation_id}/messages`

Autenticado (JWT). Roles: `admin`, `vendedor` (con `can_send`).

### Request

```json
{
  "message_type": "text",
  "text": "contenido del mensaje",
  "client_request_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
}
```

- `message_type`: solo `"text"` en 1I.1.
- `text`: se normaliza (`CRLF`/`CR`→`LF`); no puede quedar vacío tras `strip()`; máx. 4096
  (sobre el texto canónico).
- `client_request_id`: **UUID válido** (autoridad única de idempotencia; no hay header).
- Cuerpo estricto (`extra=forbid`).

### Respuesta exitosa

```json
{
  "message": {
    "id": 123,
    "conversation_id": 45,
    "direction": "outbound",
    "message_type": "text",
    "text_body": "contenido del mensaje",
    "current_status": "accepted",
    "provider_timestamp": null,
    "sender_user_id": 7,
    "created_at": "2026-07-30T14:00:00Z"
  },
  "accepted": true,
  "duplicate": false,
  "outcome": "accepted"
}
```

`message` reutiliza `MessageOut`: **no** expone `external_message_id` (wamid),
`client_request_id`, destinatario, `phone_number_id`, `waba_id` ni error técnico crudo.

- `accepted`: Meta aceptó (hay wamid).
- `duplicate`: replay idempotente del mismo `client_request_id`.
- `outcome`: `accepted` | `failed` | `unknown`.

### Códigos HTTP por resultado

| situación | HTTP | body |
|---|---|---|
| primer envío aceptado (con wamid) | `201` | `accepted=true, duplicate=false, outcome=accepted` |
| resultado ambiguo (timeout/5xx/caída/excepción) | `202` | `accepted=false, outcome=unknown` |
| `accepted` del proveedor **sin** identificador (wamid) | `202` | `accepted=false, outcome=unknown` |
| resultado del proveedor con `outcome` inválido | `202` | `accepted=false, outcome=unknown` |
| fallo definitivo del proveedor | `200` | `accepted=false, outcome=failed` |
| replay idempotente | `200` | `duplicate=true, outcome` según el estado existente |

Los estados `unknown` guardan internamente un `error_code` estable
(`WHATSAPP_ACCEPTED_WITHOUT_EXTERNAL_ID`, `WHATSAPP_INVALID_SENDER_RESULT`,
`WHATSAPP_SENDER_EXCEPTION`) que **no** se expone en la respuesta. Ningún `unknown` se
reintenta automáticamente.

### Errores (no se crea/duplica mensaje)

El detalle es un objeto `{"code": "...", "message": "..."}` con un **código estable**:

| HTTP | code | motivo |
|---|---|---|
| `503` | `WHATSAPP_OUTBOUND_DISABLED` | feature flag apagado |
| `404` | `WHATSAPP_CONVERSATION_NOT_FOUND` | inexistente o no autorizada (IDOR-safe) |
| `403` | `WHATSAPP_SEND_FORBIDDEN` | usuario sin `can_send` en la línea |
| `409` | `WHATSAPP_LINE_INACTIVE` | línea inactiva |
| `422` | `WHATSAPP_TEXT_EMPTY` | texto vacío / solo espacios |
| `422` | `WHATSAPP_TEXT_TOO_LONG` | texto canónico > 4096 |
| `422` | `WHATSAPP_UNSUPPORTED_MESSAGE_TYPE` | `message_type` ≠ `text` |
| `409` | `WHATSAPP_TEMPLATE_REQUIRED` | ventana de 24 h cerrada / NULL |
| `409` | `WHATSAPP_RECIPIENT_UNAVAILABLE` | el contacto no tiene destinatario válido |
| `409` | `WHATSAPP_SEND_IN_PROGRESS` | ya hay una salida en vuelo en la conversación |
| `409` | `WHATSAPP_IDEMPOTENCY_MISMATCH` | mismo `client_request_id`, contenido distinto |

`422` también lo devuelve pydantic si `client_request_id` no es un UUID o el body trae
campos extra.

### Idempotencia (resumen)

Reintentar con el **mismo** `client_request_id` + misma conversación + mismo texto canónico
devuelve el mensaje ya creado (`duplicate=true`) sin reinvocar al sender — incluso si ese
mensaje quedó `unknown`. Cambiar conversación, tipo o texto con el mismo id → `409
WHATSAPP_IDEMPOTENCY_MISMATCH`.

### Notas de seguridad

- No se expone la respuesta cruda de Meta ni el wamid.
- El destinatario se resuelve de los identificadores del contacto y nunca se devuelve.
- Los logs no contienen texto, teléfono, `wa_id`, token ni el `external_message_id`
  completo (ver `services/whatsapp/redaction.py`).

### Fuera de alcance en 1I.1

Envío real a Meta, templates, media, reintento automático de `unknown`, y actualización de
estados vía webhook (`sent/delivered/read/failed`) — llegan en 1I.2.

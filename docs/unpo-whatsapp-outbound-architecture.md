# WhatsApp — Arquitectura de mensajería saliente (Etapa 1I.1)

Núcleo backend para **enviar mensajes de texto salientes** desde el CRM. Esta etapa
implementa toda la lógica local, transaccional y de seguridad **sin hablar con Meta**: el
cliente HTTP real llega en 1I.2. El envío se prueba con un `sender` inyectable/falso.

## Alcance de 1I.1

Incluye: endpoint autenticado, permisos, resolución segura del destinatario, ventana de
atención de 24 h, reserva previa, idempotencia por `client_request_id`, estados internos,
"una salida en vuelo por conversación", y un `WhatsAppSender` inyectable con una
implementación `DisabledWhatsAppSender` (runtime, sin red) y `FakeWhatsAppSender` (tests).

**Fuera de alcance (1I.1):** llamada real a Meta, access tokens, templates, media, cambios
al webhook de estados, recovery/reconciliador de salientes, frontend, migraciones.

## Feature flag

`WHATSAPP_OUTBOUND_ENABLED` (default **false**). Con el flag apagado el endpoint responde
`503 WHATSAPP_OUTBOUND_DISABLED` y **no crea ninguna fila**. En 1I.1 no hay sender real ni
access token: el flag permite integrar el núcleo sin exponer envío. No se leen ni se crean
nombres de secretos adicionales en esta etapa.

## Modelo de datos

No requiere migración: el esquema 1B (`efa066dfdf30`) ya fue diseñado para salientes.
`whatsapp_messages` aporta `client_request_id` (UUID, **único parcial**),
`external_message_id` (**único parcial**), `current_status`, `direction`, `origin`,
`sender_user_id`, `error_code`, `error_message_safe`.

## Estados internos

| estado | significado | origen |
|---|---|---|
| `pending` | reservado, aún no se llamó al sender | local |
| `sending` | se está invocando al sender | local |
| `accepted` | Meta aceptó; hay `external_message_id` (wamid) | respuesta del sender |
| `sent` / `delivered` / `read` | avance del webhook (1I.2) | Meta |
| `failed` | rechazo definitivo | sender / webhook |
| `unknown` | **resultado ambiguo** (timeout/desconexión/5xx/caída) | local |

Precedencia central reutilizada de `processor.next_current_status` (`pending < accepted <
sent < delivered < read`; `failed` solo lo superan `delivered`/`read`). `unknown` es un
estado local que solo se aplica si el mensaje sigue en `pending`/`sending`.

Regla absoluta: **`unknown` nunca se reenvía automáticamente**. Un replay del mismo
`client_request_id` devuelve el mensaje `unknown` y no vuelve a invocar al sender.

## Idempotencia

Autoridad **única**: `client_request_id` (UUID) en el body. No hay `Idempotency-Key`
header. Índice único parcial `uq_whatsapp_messages_client_request_id`.

- Replay (misma conversación, `type=text`, mismo texto canónico) → devuelve el mensaje
  existente con `duplicate=true`, sin reinvocar al sender.
- Mismo `client_request_id` con conversación / tipo / texto distinto → `409
  WHATSAPP_IDEMPOTENCY_MISMATCH` (no filtra info de una conversación ajena).

**Texto canónico:** `CRLF`/`CR` → `LF`; se rechaza si `strip() == ""`; máximo 4096
caracteres. Se persiste y se compara siempre la misma representación canónica (no se
eliminan saltos ni espacios internos).

## Una salida en vuelo por conversación

Mientras exista otro mensaje `outbound` en `pending`, `sending` o `unknown`, un nuevo envío
responde `409 WHATSAPP_SEND_IN_PROGRESS`. Se garantiza incluso con requests concurrentes y
`client_request_id` distintos, mediante `SELECT ... FOR UPDATE` sobre la conversación y la
consulta de "en vuelo" dentro de esa sección crítica. Los estados `accepted`, `sent`,
`delivered`, `read`, `failed` **no** bloquean. No requiere constraint nuevo ni migración.

## Resolución del destinatario

`resolve_meta_recipient(db, contact_id)` en orden estricto de preferencia:

1. `wa_id` primario · 2. `wa_id` no-primario · 3. `phone_e164` primario · 4. `phone_e164`

Dentro de cada grupo se recorren **todos** los candidatos por `id` ascendente (determinista),
se **ignoran los inválidos** y se devuelve el primer válido (no se descarta el grupo entero
por un primer candidato inválido). Valida el formato básico **sin modificar** el valor.

Formato de `phone_e164`: el normalizer inbound persiste `+`+dígitos
(`normalize_wa_id_to_e164` → `+549…`); por robustez también se acepta el formato histórico
de **solo dígitos** (`549…`), y el valor se pasa al sender tal cual. `wa_id` es dígitos sin
`+`.

NUNCA usa el `display_number` de la línea, el `phone_masked`, el nombre del contacto ni el
teléfono del lead/vendedor. Sin identificador válido → `409 WHATSAPP_RECIPIENT_UNAVAILABLE`.
El destinatario nunca aparece en respuestas ni logs.

## Ventana de atención (24 h)

Se usa `conversation.customer_service_window_expires_at` (mantenido por el procesador
inbound). Con margen de 60 s y reloj UTC: se permite texto libre si
`now_utc < expires - 60s`. Si el campo es NULL o la ventana está cerrada → `409
WHATSAPP_TEMPLATE_REQUIRED` (*fail-closed*). El backend valida siempre; no confía en el
frontend. No se implementan templates en 1I.1.

## Permisos

- **Admin:** requiere línea activa; `can_send` efectivo (siempre, por la política vigente).
- **Vendedor:** conversación autorizada (asignada o `can_view` de la línea) **y**
  `can_send=true` explícito en la línea. La asignación por sí sola NO concede `can_send`.
- Conversación fuera de scope → `404` (IDOR-safe; conocer el `conversation_id` no amplía
  acceso). Rol no permitido → `403`.

## Flujo transaccional

1. flag → 2. auth → 3. IDOR (`get_authorized_conversation`) → 4. lock `FOR UPDATE` +
revalidar autorización → 5. línea activa → 6. `can_send` → 7. idempotencia (replay/mismatch)
→ 8. ventana → 9. destinatario → 10. "una en vuelo" → 11. reserva `pending` + **commit
corto** (libera el lock) → 12. **CAS obligatorio** `pending→sending` (UPDATE condicional,
`rowcount == 1`) → 13. **invocar al sender FUERA de transacción** → 14. `apply_result`
(recarga con lock; compare-and-set; sin retroceder `sent/delivered/read`) → 15. respuesta
segura.

Una caída/timeout/desconexión durante el envío se traduce a **ambiguo** ⇒ `unknown`.

## Robustez de transiciones (1I.1b)

- **CAS obligatorio** `pending→sending`: solo se invoca al sender si el UPDATE condicional
  (`WHERE current_status='pending'`) afectó exactamente una fila. Si falla, NO se envía: se
  relee el mensaje y se devuelve replay idempotente (misma solicitud) o un error interno
  estable si el estado es inconsistente. Garantía: **nunca** se envía sobre un mensaje que
  ya avanzó (delivered/failed/etc.).
- **`accepted` exige `external_message_id`**: si el sender responde `accepted` pero el id
  es null/vacío/whitespace, NO se guarda `accepted`: queda `unknown` con
  `error_code=WHATSAPP_ACCEPTED_WITHOUT_EXTERNAL_ID` (sin auto-reintento).
- **Outcome inválido**: un `outcome` fuera de `{accepted, definitive_failure, ambiguous}`
  NO entra como `definitive_failure`: se trata como `unknown` con
  `error_code=WHATSAPP_INVALID_SENDER_RESULT`.
- **Excepción del sender**: una excepción al invocar al sender se convierte en `unknown`
  (`error_code=WHATSAPP_SENDER_EXCEPTION`, `error_message_safe` literal fijo). El log
  registra **solo** `message_id` y `exception_type=type(exc).__name__` — nunca
  `str/repr/args` de la excepción (podrían traer texto, destinatario, URL o token).

## Sender inyectable

`services/whatsapp/sender.py` define `SendTextCommand`, `SendResult` y el `Protocol`
`WhatsAppSender.send_text(command) -> SendResult` (`accepted|definitive_failure|ambiguous`).
`DisabledWhatsAppSender` (runtime) **no hace red**. Los tests inyectan `FakeWhatsAppSender`
vía `app.dependency_overrides[get_whatsapp_sender]`. Esta etapa **no** importa `httpx`,
`requests` ni `graph.facebook.com`.

## Logs y seguridad

Se reutiliza `redaction.py`. Se loguean solo: `internal_message_id`, `conversation_id`,
`line_id`, `user_id`, estado, HTTP status, `error_code` seguro, duración y un hash corto de
`client_request_id`. Nunca: texto, destinatario, teléfono, `wa_id`, JWT, token, payload,
respuesta cruda del sender ni `external_message_id` completo.

## Riesgos pendientes para 1I.2

- **Status antes del wamid:** un `sent`/`delivered` del webhook puede llegar antes de
  persistir el `external_message_id`; hoy el procesador lo descarta como desconocido. 1I.2
  debe re-correlacionar (evento webhook retryable) — **no se toca el webhook en 1I.1**.
- **Reconciliador de salientes:** mensajes en `sending`/`unknown` por crash necesitan un
  proceso que los cierre; `unknown` nunca se auto-reenvía.
- **Cliente Meta real:** timeouts, mapeo de error codes (auth/rate-limit/re-engagement),
  y resolución del access token por línea.

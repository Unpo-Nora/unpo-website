# UNPO — API del inbox multiagente de WhatsApp (Etapa 1G)

API autenticada del inbox unificado de WhatsApp: líneas accesibles, listado y detalle de
conversaciones, historial de mensajes, no leídos por usuario, marcado de leído, asignación
y su historial. Todo con autorización estricta por usuario y por línea.

- Router: [`backend/app/routers/whatsapp_inbox.py`](../backend/app/routers/whatsapp_inbox.py)
  (separado del webhook público [`routers/whatsapp.py`](../backend/app/routers/whatsapp.py)).
- Lógica de acceso/consultas: [`services/whatsapp/inbox.py`](../backend/app/services/whatsapp/inbox.py).
- Schemas de respuesta/request: [`schemas_whatsapp_inbox.py`](../backend/app/schemas_whatsapp_inbox.py).
- Tests: [`tests/test_whatsapp_inbox.py`](../backend/tests/test_whatsapp_inbox.py).

Prefijo: todas las rutas cuelgan de `/whatsapp` (sin `/api/v1`, consistente con el backend).

## Autenticación y roles

- **JWT Bearer** obligatorio en todas las rutas (`get_current_user`). Sin token o token
  inválido → **401**.
- Roles válidos: `admin` y `vendedor` (se validan con `require_roles`; un rol fantasma es
  rechazado). Las rutas de lectura aceptan ambos; la asignación es **solo admin**.

## Autorización

| Actor | Acceso |
|---|---|
| **admin** | Todas las líneas y conversaciones. Único que puede asignar/reasignar y ver cualquier historial. |
| **vendedor** | Una conversación es accesible si está **asignada a él/ella** **o** si tiene acceso a la **línea** vía `whatsapp_line_user_access.can_view`. |

- **Protección IDOR**: el acceso denegado a una conversación responde **404** (no se filtra
  su existencia). Conocer el `conversation_id` no otorga acceso.
- La asignación (`PATCH .../assignment`) exige rol admin → **403** para el resto.
- Toda búsqueda aplica **primero** el filtro de autorización y **después** el término, de
  modo que nunca expone conversaciones fuera del alcance del usuario.

## Endpoints

### `GET /whatsapp/lines`
Líneas del **alcance efectivo** del usuario. Admin: todas. Vendedor:
`effective_line_ids = líneas con can_view=true  UNION  líneas de conversaciones
asignadas al usuario`. Una línea incluida **solo por asignación** aparece con
`can_view=true` y `can_send=false` (salvo un `can_send=true` explícito en
`whatsapp_line_user_access`). El acceso por asignación **no** se convierte en acceso
global a la línea (ver «Alcance efectivo de líneas»). Cada ítem: `id, label,
display_number, provider, is_active, can_view, can_send`. **No** expone `phone_number_id`
ni `waba_id`.

### `GET /whatsapp/conversations`
Listado paginado. **Filtros** (query params):

| Param | Tipo | Efecto |
|---|---|---|
| `line_id` | int | Conversaciones de esa línea. |
| `assigned_user_id` | int | Asignadas a ese usuario. |
| `assigned_to_me` | bool | Asignadas al usuario actual. |
| `unassigned` | bool | Sin asignar. |
| `unread_only` | bool | Con al menos un no leído para el usuario actual. |
| `status` | str | `open` / `closed` / `archived`. |
| `search` | str (≤100) | Nombre de contacto o identificador (wa_id/teléfono), tratado como literal. |
| `limit` | int 1..100 (def. 30) | Tamaño de página. |
| `offset` | int ≥0 (def. 0) | Desplazamiento. |

Orden: por `coalesce(last_message_at, created_at)` desc, `id` desc. Respuesta:
`{ items[], limit, offset, count, has_more }`. Cada ítem incluye `conversation_id`, `line`
(id/label/display_number), `status`, `contact` (nombre + teléfono **enmascarado**),
`assigned_user` (id/nombre/rol o `null`), `last_message_at`, dirección/tipo del último
mensaje, `last_message_preview` (≤120 chars) y `unread_count` del usuario actual.

### `GET /whatsapp/conversations/{id}`
Detalle autorizado: `line`, `contact` (enmascarado), `lead_id`, `assigned_user`,
`status`, `unread_count`, y timestamps (`last_message_at`, `last_inbound_at`, `created_at`,
`updated_at`). No accesible → **404**.

`lead_id` se devuelve **solo si el usuario está autorizado a LEER ese lead** según la
política canónica de leads (`crud.can_read_lead`): admin siempre; vendedor si el lead es
propio (`lead.seller == su email`) o está en estado `NEW`. Un vendedor con acceso a la
conversación pero **no al lead** (lead de otro vendedor) recibe `lead_id=null`; nunca se
responde 403 ni se revela por otra vía que el lead existe.

### `GET /whatsapp/conversations/{id}/messages`
Historial paginado por **keyset/cursor** (mecanismo canónico). Los `items` **siempre** se
devuelven en orden `created_at ASC, id ASC` (para renderizar el chat de antiguo a nuevo).
Params:

- `limit` (1..100, def. 50);
- `direction` (`forward` | `backward`, def. `forward`) — **paginación bidireccional (1H)**:
  - `forward` (retrocompatible con 1G): sin `cursor` → primeros mensajes; con `cursor` →
    mensajes **posteriores** (`created_at > c OR (== AND id > c_id)`);
  - `backward`: sin `cursor` → **últimos N** mensajes; con `cursor` → mensajes **anteriores**
    (`created_at < c OR (== AND id < c_id)`). Internamente consulta DESC para limitar y
    revierte a ASC en la respuesta;
- `cursor` (opaco): codifica `(last_created_at, last_id)`. Un `cursor` inválido → **422**. El
  cursor es solo una **posición**: la consulta siempre queda acotada a la conversación
  autorizada, así que un cursor de otra conversación no otorga acceso ni amplía el scope;
- `offset` (≥0): **deprecado**, solo compatibilidad forward; se ignora si viene `cursor` o
  `direction=backward`.

Respuesta `{ items[], limit, count, has_more, next_cursor, offset, older_cursor,
newer_cursor, direction }`:

- `older_cursor` deriva del **primer** item entregado → cargar mensajes anteriores con
  `direction=backward&cursor=older_cursor`;
- `newer_cursor` deriva del **último** item entregado → traer mensajes nuevos con
  `direction=forward&cursor=newer_cursor` (polling);
- `has_more` es direccional: en `forward` indica que hay mensajes más nuevos; en `backward`,
  más antiguos;
- `next_cursor` conserva su **semántica forward** de 1G (compatibilidad); es `null` en
  `backward`;
- `direction` es el sentido de la consulta que produjo la página.

Combinando páginas por `id` no hay duplicados ni saltos. Cada mensaje: `id, conversation_id,
direction, message_type, text_body, current_status, provider_timestamp, sender_user_id,
created_at`. **No** expone `external_message_id` (wamid) ni `raw_payload`. Sin migración.

### `GET /whatsapp/unread-counts`
Totales de no leídos del usuario: `{ total_unread, lines: [{ line_id, label, unread_count }] }`,
una fila por línea accesible.

### `POST /whatsapp/conversations/{id}/read`
Marca leído. Body opcional `{ "last_read_message_id": <int> }`:
- Si se envía, el mensaje **debe** pertenecer a la conversación (si no, 404).
- Si se omite, marca hasta el último mensaje de la conversación.
- **Upsert** por `(conversation_id, user_id)`; **nunca retrocede** el puntero (solo avanza).
- **Idempotente**; aislado por usuario. Respuesta: `{ conversation_id, last_read_message_id,
  unread_count }`.

**Garantías de concurrencia**: la conversación se bloquea con `SELECT ... FOR UPDATE` como
mutex por `conversation_id`, se revalida la autorización bajo el lock, y esto serializa los
marcados concurrentes cubriendo también la **creación inicial** de la fila de lectura. Bajo
carrera: ambos requests responden 200, existe **una sola** fila por `(conversation_id,
user_id)`, `last_read_message_id` solo avanza (nunca regresa) y una carrera de creación
nunca produce 500. Validado en PostgreSQL 17 con hilos concurrentes.

### `PATCH /whatsapp/conversations/{id}/assignment` — solo admin
Body `{ "assigned_user_id": <int>, "reason": <str?> }` (`extra=forbid`, sin mass-assignment).
Reglas:
- Valida que el usuario destino exista y tenga rol válido.
- Valida que el destino tenga **acceso a la línea** (`can_view`); un admin destino tiene
  acceso implícito. Sin acceso → **400**.
- Si la asignación no cambia (mismo usuario) → `changed=false`, **sin** entrada de historial.
- Si cambia: actualiza `assigned_user_id` e inserta una fila en
  `whatsapp_conversation_assignments` (`from`/`to`/`assigned_by`/`source=manual`/`reason`) en
  **una transacción atómica**.
- **Desasignar no está habilitado** en esta etapa (la arquitectura no lo autoriza): el body
  exige un `assigned_user_id` válido.

**Garantías de concurrencia**: la conversación se carga con `SELECT ... FOR UPDATE` antes de
leer `old_user_id`; la evaluación de «mismo usuario» y la revalidación del acceso del
destino a la línea ocurren **bajo el lock**, y la actualización más el historial se confirman
juntos (rollback completo ante error). Dos reasignaciones concurrentes se **serializan**: el
historial forma una **cadena lineal** donde cada `from_user_id` coincide con el estado
confirmado inmediatamente anterior (sin dos entradas basadas en el mismo estado obsoleto), y
la conversación final coincide con el último `to_user_id`. Validado en PostgreSQL 17.

Respuesta: `{ conversation_id, assigned_user_id, changed, assignment }`.

### `GET /whatsapp/conversations/{id}/assignments`
Historial cronológico (`created_at, id` asc) de una conversación accesible: `id, from_user_id,
to_user_id, assigned_by_user_id, assignment_source, reason, created_at`.

## No leídos por usuario

`unread_count` = mensajes **inbound** con `id > last_read_message_id` del usuario (de
`whatsapp_conversation_reads`). Si no hay fila de lectura, todos los inbound cuentan. Los
**outbound nunca** cuentan. El marcado de un usuario no afecta a otro. En el listado se
calcula en **una sola consulta** (LEFT JOIN), sin N+1.

## Alcance efectivo de líneas

`effective_line_ids = líneas con can_view=true  UNION  líneas de conversaciones asignadas
al usuario`. Se usa de forma consistente en `GET /whatsapp/lines` y en el desglose por línea
de `GET /whatsapp/unread-counts`. Una línea incluida **solo por asignación** aparece con
`can_view=true` y `can_send=false` (salvo `can_send=true` explícito).

Importante: el acceso por asignación **no** se convierte en acceso global a la línea. La
**visibilidad de conversaciones** (listado y detalle) sigue gobernada por
`assigned_to_me OR line_id IN {líneas con can_view}`: un vendedor asignado a una sola
conversación de una línea (sin `line_user_access`) ve **esa** conversación y la línea
aparece en su inbox, pero **no** ve las demás conversaciones no asignadas de esa línea.

## Usuario activo (limitación actual)

El modelo `User` (`id, email, hashed_password, full_name, role`) **no** tiene un campo
`is_active`/`disabled`. Por eso la validación del usuario destino en la asignación se limita
a **existencia + rol válido** (`admin`/`vendedor`); no hay validación de «usuario activo».
No se crea migración comercial para agregar el campo en esta etapa
(`active_user_validation = NOT_SUPPORTED_BY_CURRENT_USER_MODEL`).

## Códigos HTTP

| Código | Situación |
|---|---|
| 200 | OK. |
| 401 | Sin token o token inválido. |
| 403 | Rol insuficiente (p. ej. vendedor intentando asignar). |
| 404 | Conversación/mensaje inexistente **o** no autorizado (IDOR-safe). |
| 400 | Usuario destino inválido o sin acceso a la línea (asignación). |
| 422 | Validación de params (límites de paginación, body malformado). |

## Seguridad y redacción

- **Nunca** se exponen: `raw_payload`, `payload_hash`, `event_key`, App Secret, verify token,
  access tokens, `DATABASE_URL`, `phone_number_id`/`waba_id`, `hashed_password`.
- El teléfono/wa_id del contacto va **enmascarado** (`mask_identifier` → `***XXXX`).
- El término de búsqueda **no** se registra (puede contener un teléfono); solo su longitud.
- Los patrones LIKE se **escapan** (`\ % _`) y el término se trata como literal (a prueba de
  inyección SQL vía ORM parametrizado).
- Límites duros: `limit` de conversaciones ≤100, de mensajes ≤100, `search` ≤100 chars.

## Rendimiento

`EXPLAIN ANALYZE` sobre PostgreSQL 17 con ~4000 conversaciones y ~4000 mensajes: todas las
consultas calientes < 3 ms. El listado por `assigned_user_id` usa
`ix_whatsapp_conversations_assigned_status_last_msg`; los mensajes por conversación usan
`ix_whatsapp_messages_conversation_created_at`. Los listados por línea/estado hacen seq-scan
+ top-N (más barato que un índice a esta escala). **No se agregó ninguna migración**: los
índices existentes cubren los accesos y ningún `EXPLAIN` demostró una necesidad concreta a la
escala de un inbox de dos vendedores.

## Fuera de alcance de esta etapa (1G)

- Frontend / UI del inbox.
- Tiempo real (SSE/WebSocket) — el MVP usa **polling** (arquitectura §8).
- **Envío** de mensajes salientes (`POST .../messages`), archivos/media.
- Conversión a lead, cierre/reapertura de conversación.
- Automatizaciones de IA.
- Conexión de líneas productivas y cualquier cosa de **NORA**.

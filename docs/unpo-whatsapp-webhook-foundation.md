# UNPO — Fundación del webhook de WhatsApp Cloud API (Etapa 1C)

> Documento técnico de la **implementación** de recepción de webhooks. La fuente de
> verdad de la arquitectura sigue siendo
> [`unpo-whatsapp-cloud-api-architecture.md`](./unpo-whatsapp-cloud-api-architecture.md);
> acá se documenta cómo quedó implementado lo que ese documento define en §6, §7 y §9.
>
> **Alcance:** solo recepción. Esta etapa **no** se conecta a Meta, **no** envía
> mensajes, **no** usa credenciales reales, **no** despliega, **no** conecta números
> productivos, **no** toca el frontend y **no** toca NORA.

## 1. Rutas

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| `GET` | `/whatsapp/webhook` | verify token (query) | Handshake de verificación de Meta |
| `POST` | `/whatsapp/webhook` | firma `X-Hub-Signature-256` | Recepción de eventos |

Ambos endpoints son **públicos respecto del JWT interno**: Meta no envía tokens del
CRM. La autenticación del `GET` es el verify token y la del `POST` es la firma HMAC.
No se registran otros métodos: `PUT`, `PATCH` y `DELETE` responden **405**.

## 2. Variables de entorno

```text
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_META_APP_SECRET=
```

Documentadas en [`backend/.env.example`](../backend/.env.example) (solo nombres).

Se usan nombres propios y no `META_VERIFY_TOKEN` / `META_APP_SECRET` porque esos ya
pertenecen a los webhooks de **Lead Ads** (`app/routers/leads.py`) y la arquitectura
§3 define una **aplicación de Meta separada** para WhatsApp. La convención sigue la
del proyecto (`NORA_META_VERIFY_TOKEN`): prefijo por ámbito.

Ninguna de las dos se almacena en la base de datos. `whatsapp_lines` guarda solo
configuración **no secreta** de las líneas.

### Comportamiento sin configuración

| Situación | Respuesta |
|---|---|
| `WHATSAPP_VERIFY_TOKEN` ausente | `GET` → **503** (no se valida contra cadena vacía) |
| `WHATSAPP_META_APP_SECRET` ausente | `POST` → **503** (la firma es obligatoria, nunca se omite) |

> Diferencia deliberada con el webhook de Lead Ads de NORA, que omite la firma cuando
> no hay App Secret configurado: acá **no existe** ese modo permisivo.

## 3. Verificación (GET)

Devuelve `hub.challenge` en texto plano con **200** solo si:

- `hub.mode == "subscribe"`, y
- `hub.verify_token` coincide con el configurado (`hmac.compare_digest`, tiempo constante).

Cualquier otro caso — token inválido, modo inválido o parámetros faltantes — responde
**403** con el mismo mensaje genérico: no se distingue el motivo para no dar un oráculo.
El verify token no se registra en logs ni se devuelve en la respuesta.

## 4. Validación de firma (POST)

```text
X-Hub-Signature-256: sha256=<digest hexadecimal>
```

- HMAC-SHA256 sobre el **cuerpo crudo en bytes**, leído **una sola vez** y **antes** de
  parsear el JSON.
- Comparación con `hmac.compare_digest`.
- Se rechaza (**403**) si falta la cabecera, si el prefijo no es exactamente `sha256=`,
  si el digest no es hexadecimal o si no coincide (incluye el caso "cuerpo modificado
  después de firmar").
- La lógica vive en `app/services/whatsapp/signature.py`, fuera del router, y no está
  duplicada.

Otros códigos del `POST`: **400** JSON inválido con firma válida · **413** cuerpo mayor
a `MAX_WEBHOOK_BODY_BYTES` (1 MiB, protección local de este endpoint; el proyecto no
tiene middleware global de tamaño y no se agregó uno para no alterar la subida de
imágenes ni los importadores) · **500** si el evento **no** pudo almacenarse · **200**
si el evento quedó almacenado.

## 5. Idempotencia

### 5.1 Evento (`whatsapp_webhook_events`)

Meta no entrega un identificador único a nivel de webhook, así que la clave es
**determinística por contenido**:

```text
payload_hash = sha256(JSON canónico: claves ordenadas, sin espacios)
event_key    = "sha256:<payload_hash>"
```

`unique(provider, event_key)` + relectura ante `IntegrityError` (protección final ante
concurrencia). Un reintento de Meta devuelve **200** con `{"status": "duplicate"}` y no
reprocesa nada. No se usa timestamp de recepción ni UUID aleatorio: ninguno deduplica.

### 5.2 Mensajes (`whatsapp_messages`)

Dedupe por `external_message_id` (el `wamid` de Meta), respaldado por el índice único
parcial `unique(provider, external_message_id) WHERE external_message_id IS NOT NULL`.
El mismo mensaje reenviado dentro de otro webhook **no** crea un registro nuevo.

### 5.3 Estados (`whatsapp_message_status_events`)

Clave estable por evento de estado:

```text
event_key = "meta:<external_message_id>:<status>:<timestamp de Meta>"
```

(si excediera 255 caracteres se usa un hash del mismo contenido). `unique(event_key)`
más captura de `IntegrityError`. La tabla es **append-only**: el historial se conserva.

## 6. Estrategia transaccional

1. Validar firma.
2. Persistir el evento crudo y **confirmar** (`commit`).
3. Procesar cada elemento soportado **en su propia transacción**.
4. Marcar `processing_status`, `processed_at`, `attempt_count` y `last_error_safe`.
5. Responder **200**.

Si falla el paso 2 → **500** (Meta reintenta; no hubo almacenamiento). Si el evento
quedó almacenado pero falla el procesamiento → se registra el error **sanitizado**, el
evento queda en `failed` con su `raw_payload` para reproceso y se responde **200**
(arquitectura §7: la fuente de verdad y el reintento viven en la tabla).

Un elemento defectuoso no arrastra a los demás: se hace `rollback` de ese ítem y se
continúa con el siguiente. No se usan SAVEPOINTs (se comportan distinto en SQLite y
PostgreSQL). No se introdujeron Redis, Celery, Kafka ni servicios externos.

Estados de `processing_status`: `processed` (hubo al menos un elemento manejado),
`ignored` (nada aplicable: objeto/field/tipo no soportado, línea desconocida o
inactiva, estado de un mensaje que no conocemos) y `failed` (hubo errores).

## 7. Resolución de línea

Por `value.metadata.phone_number_id` contra `whatsapp_lines.phone_number_id`
(`provider = 'meta'`).

| Caso | Comportamiento |
|---|---|
| Línea conocida y activa | Se procesa |
| Línea **desconocida** | Se guarda el webhook, se registra el motivo (`unknown_line`) y **no** se crea una línea automáticamente |
| Línea **inactiva** | No se procesa nada comercial; el evento queda almacenado (`inactive_line`) |

UNPO y NORA no se mezclan: la separación es por línea y esta etapa no carga ninguna
línea productiva. Los tests usan líneas ficticias.

## 8. Contactos, conversaciones y mensajes

**Contactos.** Se resuelven por identificadores estables: primero `wa_id` y, como
respaldo, el teléfono E.164 derivado (`+` + dígitos, solo si el `wa_id` es numérico y
de largo plausible). Solo se crea un contacto cuando no hay coincidencia segura, y se
crean/completan las filas de `whatsapp_contact_identifiers`.

> **Regla de negocio:** un contacto desconocido **NO** se convierte en lead. Se crean
> contacto, identificadores y conversación, pero **nunca** un registro en `leads`;
> `lead_id` queda en `NULL`. La conversión a lead será manual, en una etapa posterior.

**Conversaciones.** Una por `(línea, contacto)` — el modelo tiene
`unique(line_id, contact_id)`. Un mensaje entrante sobre un hilo cerrado lo **reabre**
(no puede existir un segundo hilo para el mismo par). La misma persona escribiendo a
otra línea produce otra conversación. Se actualizan `last_message_at`,
`last_inbound_at` y `customer_service_window_expires_at` (24 h). **No** se asigna
vendedor: `assigned_user_id` queda en `NULL` y la conversación queda "sin asignar",
disponible para administradores en una etapa posterior. No se toca la rotación de
leads ni el sistema de asignación comercial existente.

**Mensajes.** Solo entrantes de tipo `text`: `direction='inbound'`,
`message_type='text'`, `current_status='delivered'` (ya nos fue entregado),
`origin='cloud_api'`, `provider_timestamp` desde el timestamp de Meta,
`context_external_message_id` cuando el mensaje cita a otro.

**Tipos no soportados todavía:** `image`, `video`, `audio`, `document`, `sticker`,
`location`, `contacts`, `interactive`, `reaction`. No rompen el webhook: el evento se
registra, el elemento se marca como no soportado y **no** se fabrica un mensaje de
texto. No se crea `whatsapp_media`.

## 9. Estados de mensajes

Soportados: `sent`, `delivered`, `read`, `failed`. Precedencia explícita:

```text
pending < accepted < sent < delivered < read
```

- Un estado **nunca retrocede**: `delivered` llegando después de `read` no baja el
  estado actual.
- `failed` se aplica salvo que ya exista prueba de entrega (`delivered`/`read`).
- Desde `failed`, solo una confirmación real de entrega/lectura puede superarlo.
- Para `failed` se guardan `error_code` y `error_message_safe` (sanitizado, una línea,
  acotado). El `safe_payload` del evento guarda el estado, el destinatario
  **enmascarado** y el código/título del error — nunca el teléfono completo.
- Un estado de un mensaje externo que no conocemos se ignora sin romper.

Todos los estados son `String` (arquitectura §5): no se creó ningún enum PostgreSQL.

## 10. Logging

Se registra de forma estructurada: webhook aceptado, firma inválida, evento duplicado,
línea desconocida/inactiva, mensaje procesado, estado procesado, tipo/field/objeto no
soportado y fallo de procesamiento.

**Nunca** se registran: cuerpo completo, teléfono completo, nombre del contacto,
contenido del mensaje, tokens, secretos ni la firma. Para correlacionar se usan IDs
internos (`line_id`, `conversation_id`, `contact_id`, `message_id`), hashes truncados
(`sha256:60e91a0f6eff…`) e identificadores enmascarados (`***0000`).

## 11. Archivos

```text
backend/app/routers/whatsapp.py                    router delgado (GET/POST)
backend/app/schemas_whatsapp.py                    envelope mínimo y tolerante
backend/app/services/whatsapp/config.py            variables de entorno y límites
backend/app/services/whatsapp/signature.py         HMAC-SHA256
backend/app/services/whatsapp/redaction.py         helpers de logging seguro
backend/app/services/whatsapp/normalizer.py        normalización + claves determinísticas
backend/app/services/whatsapp/events.py            persistencia e idempotencia del evento
backend/app/services/whatsapp/processor.py         línea, contacto, conversación, mensajes, estados
backend/tests/whatsapp_fixtures.py                 payloads ficticios (TEST_*)
backend/tests/test_whatsapp_webhook.py             suite de la etapa
```

Los schemas Pydantic modelan **solo** el envelope mínimo (entry / changes / value /
metadata / contacts / messages / statuses) con `extra="allow"` y todos los campos
opcionales: si Meta agrega un campo desconocido, el procesador no falla.

## 12. Cómo ejecutar los tests

Dentro del contenedor del backend (o cualquier entorno con `requirements.txt`
instalado), desde `backend/`:

```bash
# suite de esta etapa
python -m unittest tests.test_whatsapp_webhook -v

# suite completa del backend
python -m unittest discover -s tests -t .
```

Contenedor efímero, sin puertos ni base de datos (los tests usan SQLite en memoria):

```bash
docker run --rm -v "$PWD/backend:/app" -w /app --entrypoint python \
  unpo-website-backend:latest -m unittest discover -s tests -t .
```

No hace falta `DATABASE_URL`: la suite crea el esquema desde `Base.metadata` sobre
SQLite en memoria con `PRAGMA foreign_keys=ON`. **Alembic sigue siendo el único gestor
del esquema PostgreSQL** (head `efa066dfdf30`); esta etapa **no** agregó migraciones.

## 13. Limitaciones de esta etapa

- No hay conexión con Meta, ni envío de mensajes, ni plantillas, ni media.
- No hay procesador persistente de reintentos: los eventos en `failed` quedan
  almacenados y esperan la etapa siguiente (1E) para reprocesarse.
- No hay endpoints de bandeja, ni asignación, ni lectura, ni polling/SSE (frontend
  intacto).
- No hay conversión automática a lead ni asignación automática de vendedor.
- No hay purga automática del `raw_payload` vencido: solo se marca
  `raw_payload_expires_at` (30 días).
- No se cargaron líneas productivas ni se configuró nada en el panel de Meta.

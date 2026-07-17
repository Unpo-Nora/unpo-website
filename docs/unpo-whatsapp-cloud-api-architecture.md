# UNPO — Arquitectura WhatsApp Cloud API multiagente

> **Fuente de verdad** para la integración de WhatsApp Cloud API multiagente en el CRM de
> UNPO. Este documento es **normativo** para las etapas siguientes (1B en adelante): cualquier
> modelo, migración, endpoint o configuración debe ser consistente con lo aquí definido, o
> actualizar primero este documento.
>
> **Estado:** arquitectura **aprobada con correcciones** (Etapa 1A → 1A.1).
> **Alcance de esta etapa (1A.1):** exclusivamente documental. No incluye modelos, migraciones,
> endpoints, configuración de Meta ni deploy.

## Estado del repositorio al registrar este documento

| Ítem | Valor |
|---|---|
| Repositorio | `Unpo-Nora/unpo-website` |
| Rama base | `main` |
| HEAD base | `4fe776b` |
| Working tree | limpio |
| Alembic head | `71e9e987f7d2` |
| Rama de este documento | `docs/unpo-whatsapp-cloud-api-architecture` |

---

## 1. Estado actual (relevamiento)

Situación del código **antes** de cualquier trabajo de WhatsApp Cloud API:

- **No existe WhatsApp Cloud API** en el código. No hay `phone_number_id`, `messaging_product`
  ni cliente de mensajería de WhatsApp.
- **Los contactos actuales usan enlaces `wa.me`** (click-to-chat), tanto en la web pública UNPO
  como en el CRM. No hay recepción ni envío programático de mensajes.
- **Los leads web de UNPO alternan entre las dos líneas comerciales actuales** (rotación por
  `source = WEB_UNPO` en `crud.create_lead`). NORA usa una línea fija propia.
- **`Lead.seller`** contiene el **email** del vendedor asignado (no es FK).
- **`Lead.assigned_seller_phone`** contiene la **línea** asignada al lead.
- **Existen webhooks de Meta Lead Ads** (ingesta de leads de Facebook/Instagram) en
  `backend/app/routers/leads.py`, pero **no** de WhatsApp. El webhook de NORA valida firma
  `X-Hub-Signature-256`; el de UNPO hoy no la valida.
- **Backend:** FastAPI + SQLAlchemy **síncrono** (`psycopg2`), desplegado en **Render**, base de
  datos **Supabase PostgreSQL**.
- **Frontend:** Next.js (App Router) desplegado en **Vercel**.
- **No existe Redis, Celery, WebSocket ni worker persistente.** El único mecanismo asíncrono es
  `BackgroundTasks` de FastAPI (usado hoy para optimización de imágenes), in-process.
- **Alembic es el único gestor del esquema** (la baseline `71e9e987f7d2` es la raíz; el arranque
  del backend ya **no** ejecuta `Base.metadata.create_all()`).

> Este documento no incluye datos personales de leads ni secretos de ningún tipo.

---

## 2. Decisiones de negocio aprobadas

| Tema | Decisión aprobada |
|---|---|
| **Bandeja** | Una sola bandeja para todas las líneas, con filtros. |
| **Vendedor** | Solo puede ver y responder conversaciones **asignadas** y líneas **autorizadas**. |
| **Administrador** | Puede ver, responder y **reasignar** todas. |
| **Contacto desconocido** | Crea contacto y conversación; **no** crea lead automáticamente. |
| **Conversión a lead** | **Manual**; estado inicial `NEW`. |
| **Sin asignar** | Bandeja visible para administradores. |
| **Reasignación** | **Administrador únicamente** en el MVP. |
| **Fuera de horario** | Guardar mensajes; **sin** respuesta automática en el MVP. |
| **Historial anterior** | **No** importar en el MVP. |
| **Alcance del MVP** | Texto, estados, asignaciones, historial y no leídos. |
| **Tiempo real inicial** | **Polling**. |
| **IA** | Solo en una etapa posterior; primero **sugerencias con aprobación humana**. |

---

## 3. Estrategia Meta

| Componente | Decisión |
|---|---|
| **Business Portfolio** | Reutilizar el Business Portfolio de UNPO. |
| **Meta App** | Crear una aplicación **separada** para WhatsApp (distinta de la de Lead Ads). |
| **WABA** | Propiedad de UNPO. |
| **Token** | System User Token, **solo** en variables de entorno. |
| **App Secret** | **Solo** en variables de entorno. |
| **Configuración no secreta de líneas** | En base de datos (tabla `whatsapp_lines`). |

### 3.1 Coexistencia (secuencia aprobada)

1. Utilizar **primero** el número de prueba proporcionado por Meta.
2. Validar **recepción, envío, firma e idempotencia** con ese número de prueba.
3. Comprobar **elegibilidad de Coexistence** para las líneas existentes.
4. Incorporar **una sola** línea productiva como **piloto**.
5. Verificar operación **desde el CRM y desde la WhatsApp Business App** simultáneamente.
6. Incorporar la **segunda** línea únicamente **después** de aprobar el piloto.
7. Si Coexistence **no** está disponible, utilizar un **número nuevo dedicado** a Cloud API.
8. **No migrar completamente** las líneas existentes a Cloud API sin **nueva autorización**.

> **Riesgo registrado:** el onboarding puede afectar dispositivos vinculados; los cambios de
> dispositivo o reinstalaciones pueden requerir reconexión. Por eso el piloto usa **una** sola
> línea y se valida la operación dual (CRM + App) antes de sumar la segunda.

---

## 4. Modelo de datos aprobado

Convención: snake_case, inglés (dominio producto/ventas), FKs a `leads.id` / `users.id`,
timestamps `created_at` / `updated_at`. **No** se crean tablas en esta etapa; esto es el diseño
conceptual que implementará la Etapa 1B.

### 4.1 `whatsapp_lines`

Configuración **no secreta** de cada línea. **No almacenar tokens.**

```text
id
provider
phone_number_id
waba_id
display_number
label
is_active
created_at
updated_at
```

Constraints:

```text
unique(provider, phone_number_id)
unique(provider, display_number)
```

### 4.2 `whatsapp_line_user_access`

Permisos por línea y por usuario.

```text
id
line_id
user_id
can_view
can_send
is_default
created_at
```

Constraints:

```text
unique(line_id, user_id)
```

### 4.3 `whatsapp_contacts`

Representa una persona **globalmente**, independientemente de la línea. **No incluye `line_id`.**

```text
id
display_name
lead_id            (nullable)
first_seen_at
last_seen_at
created_at
updated_at
```

### 4.4 `whatsapp_contact_identifiers`

Identificadores de un contacto (un contacto puede tener varios).

```text
id
contact_id
provider
identifier_type
identifier_value
is_primary
created_at
```

Tipos previstos:

```text
wa_id
phone_e164
bsuid
```

Constraint:

```text
unique(provider, identifier_type, identifier_value)
```

### 4.5 `whatsapp_conversations`

Hilo por (línea, contacto).

```text
id
line_id
contact_id
lead_id                              (nullable)
assigned_user_id                     (nullable)
status
assignment_source
last_message_at
last_inbound_at
customer_service_window_expires_at
created_at
updated_at
```

Constraint:

```text
unique(line_id, contact_id)
```

Índices:

```text
(assigned_user_id, status, last_message_at)
(line_id, status, last_message_at)
(lead_id)
```

### 4.6 `whatsapp_conversation_reads`

Estado de lectura **por usuario** (no un `unread_count` global).

```text
id
conversation_id
user_id
last_read_message_id     (nullable)
last_read_at
```

Constraint:

```text
unique(conversation_id, user_id)
```

### 4.7 `whatsapp_messages`

El mensaje **saliente** se crea como `pending` **antes** de llamar a Meta.

```text
id
conversation_id
provider
external_message_id                  (nullable)
client_request_id                    (nullable)
direction
message_type
text_body                            (nullable)
current_status
context_external_message_id          (nullable)
sender_user_id                       (nullable)
origin
provider_timestamp                   (nullable)
received_at
created_at
updated_at
error_code                           (nullable)
error_message_safe                   (nullable)
```

Constraints (parciales, para idempotencia):

```text
unique(provider, external_message_id) WHERE external_message_id IS NOT NULL
unique(client_request_id)             WHERE client_request_id IS NOT NULL
```

### 4.8 `whatsapp_message_status_events`

Eventos de estado **append-only**.

```text
id
message_id
event_key
status
provider_timestamp
received_at
safe_payload      (nullable)
```

Constraint:

```text
unique(event_key)
```

> Un estado `read` puede implicar `delivered`; **no** se exige que todos los estados intermedios
> hayan llegado.

### 4.9 `whatsapp_webhook_events`

Cola/dedupe persistente de eventos crudos.

```text
id
provider
event_key
payload_hash
event_type
processing_status
attempt_count
received_at
processed_at              (nullable)
last_error_safe           (nullable)
raw_payload               (nullable)
raw_payload_expires_at    (nullable)
```

Constraint:

```text
unique(provider, event_key)
```

> **`event_key` debe generarse determinísticamente** (a partir del contenido del evento). **No**
> depender de un supuesto `ext_id` universal en el payload de Meta.

### 4.10 `whatsapp_conversation_assignments`

Historial de asignaciones (auditoría).

```text
id
conversation_id
from_user_id          (nullable)
to_user_id            (nullable)
assigned_by_user_id   (nullable)
assignment_source
reason                (nullable)
created_at
```

### 4.11 `whatsapp_media`

**Prevista para una segunda iteración** (fase de media). No se diseña en detalle en esta etapa.

---

## 5. Estados como `String`

Los estados nuevos se modelan inicialmente como **`String`**, validados por aplicación y
eventualmente mediante **`CHECK`**, evitando **enums PostgreSQL nativos** (para no requerir
`ALTER TYPE` en migraciones futuras). **No se crean todavía en código.**

```text
conversation:
  open
  closed
  archived

message direction:
  inbound
  outbound

message status:
  pending
  accepted
  sent
  delivered
  read
  failed

message origin:
  crm
  cloud_api
  business_app
  automation
  unknown

webhook processing:
  pending
  processing
  processed
  failed
  ignored
```

---

## 6. API aprobada

Consistente con el estilo del backend actual. **No** se introduce `/api/v1` solo para este
módulo.

```text
GET  /whatsapp/webhook
POST /whatsapp/webhook

GET  /whatsapp/conversations
GET  /whatsapp/conversations/{id}
GET  /whatsapp/conversations/{id}/messages
GET  /whatsapp/unread-counts

POST /whatsapp/conversations/{id}/messages
POST /whatsapp/conversations/{id}/assign
POST /whatsapp/conversations/{id}/read
POST /whatsapp/conversations/{id}/close
POST /whatsapp/conversations/{id}/reopen
```

Requisitos transversales de la API:

- **Paginación** en listados de conversaciones y de mensajes.
- **Ownership**: el vendedor solo accede a sus conversaciones asignadas (mismo patrón que leads
  en la Etapa 0A); el administrador accede a todas.
- **Permisos** basados en `require_roles` (roles válidos: `admin`, `vendedor`) más control por
  línea (`whatsapp_line_user_access`).
- **Filtros**: bandeja (mías / sin asignar / todas), línea, vendedor, estado, no leídas, búsqueda.
- **Idempotencia de envío** mediante **`client_request_id`** (el cliente genera el id; el backend
  deduplica).
- **Validación de línea autorizada** en el envío (`can_send`).
- **Auditoría** de asignaciones y de mensajes salientes.

---

## 7. Webhook

- **GET** para el handshake de verificación (responde `hub.challenge`).
- **POST** público con **firma `X-Hub-Signature-256` obligatoria**.
- Verificación de la firma sobre el **cuerpo original** (bytes crudos, antes de parsear).
- **Persistencia rápida** del evento (`whatsapp_webhook_events`) y **respuesta HTTP inmediata**
  (200) a Meta.
- **Procesamiento desacoplado** de la respuesta HTTP.
- **Dedupe** mediante `event_key` determinístico.
- Manejo de: **mensajes entrantes**, **estados de salientes** y **eventos desconocidos**
  (se registran e ignoran de forma segura).
- **Reintentos** controlados desde la tabla de eventos (con `attempt_count`).
- **Payload bruto con retención limitada** (`raw_payload_expires_at`).
- **Logs redactados** (sin cuerpos completos ni URLs temporales de media).

> Para el MVP se usa una **tabla persistente de eventos** (`whatsapp_webhook_events`) más un
> **procesador controlado**, **sin** introducir Redis todavía.
>
> **No** usar únicamente `BackgroundTasks` como garantía de entrega: puede **perder trabajos** si
> el proceso reinicia. `BackgroundTasks` puede disparar el procesamiento, pero la **fuente de
> verdad y el reintento** viven en la tabla persistente.

---

## 8. Tiempo real (frontend)

| Fase | Mecanismo |
|---|---|
| **MVP** | **Polling** cada 5–10 segundos. |
| **Posterior** | **SSE** (Server-Sent Events). |
| **No seleccionado inicialmente** | WebSocket, Supabase Realtime. |

Razones:

- Implementación simple.
- Compatible con Render y Vercel.
- Sin nueva infraestructura.
- Sin lock-in adicional.
- Suficiente para dos vendedores.

---

## 9. Seguridad

- **Tokens** únicamente en Render.
- **App Secret** únicamente en Render.
- **Verify Token** únicamente en Render.
- **Configuración no secreta de líneas** en PostgreSQL.
- **Firma obligatoria** del webhook.
- **No** registrar cuerpos completos en logs.
- **No** registrar URLs temporales de media.
- **Protección IDOR** (validar pertenencia por id en cada acceso).
- **Schemas Pydantic estrictos** (evitar mass-assignment de `assigned_user_id` / `lead_id`).
- **Rate limiting** de envíos.
- **Control de acceso por línea** (`whatsapp_line_user_access`).
- **Control de acceso por conversación** (ownership).
- **Auditoría** de asignaciones.
- **Auditoría** de mensajes salientes.
- **Idempotencia** de webhook (`event_key`) y de envío (`client_request_id`).
- **Retención limitada** del payload bruto.

---

## 10. Roadmap definitivo

Cada etapa usa un **PR independiente**.

```text
1A.1 — Documento de arquitectura
1B   — Modelos y migración
1C   — Configuración no secreta y permisos por línea
1D   — Webhook, firma e idempotencia
1E   — Procesador persistente de eventos
1F   — Recepción de texto
1G   — Envío de texto
1H   — Bandeja multiagente
1I   — Polling, lectura y badges
1J   — Coexistence piloto con una línea
1K   — Segunda línea
1L   — Media
1M   — Plantillas
1N   — IA con sugerencias
```

---

## 11. Fuera de alcance de esta etapa (1A.1)

- Modelos, migraciones Alembic, nuevos endpoints.
- Conexión a Supabase o consultas productivas.
- Deploy.
- Configuración en Meta.
- Registro o migración de números.
- Cualquier modificación de NORA.
- Cualquier cambio funcional en backend o frontend.

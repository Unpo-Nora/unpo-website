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

Otros códigos del `POST`: **400** JSON inválido —o con anidamiento tan profundo que
desborda la pila al recorrerlo— con firma válida · **413** cuerpo mayor a
`MAX_WEBHOOK_BODY_BYTES` (1 MiB) · **500** si el evento **no** pudo almacenarse ·
**200** si el evento quedó almacenado.

El anidamiento extremo se responde **400 y no 500** a propósito: es un problema del
payload, y un 500 haría que Meta lo reintentara indefinidamente con el mismo resultado.

El límite de tamaño es una protección **local** de este endpoint (el proyecto no tiene
middleware global de tamaño y no se agregó uno para no alterar la subida de imágenes ni
los importadores). Se aplica en dos cortes: por `Content-Length` cuando viene, y —el
que realmente protege— **acumulando el cuerpo por chunks y abortando apenas se supera
el límite**. Leer con `request.body()` bufferearía primero el cuerpo entero, así que un
cliente anónimo con `transfer-encoding: chunked` (sin `Content-Length`, y antes de que
se valide la firma) podría agotar la memoria del worker.

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
(arquitectura §7: la fuente de verdad y el reintento viven en la tabla). Eso vale
también para un fallo **fuera** de los bucles de elementos (por ejemplo una conexión
caída): se captura igual, para que el evento no quede en `pending` sin cierre. Si ni
siquiera se puede marcar el resultado, la respuesta informa `pending` —lo que dice la
fila— y nunca un `processed` que no está en la base.

Un evento con éxito parcial (algunos elementos procesados, otro con error) queda en
`failed`: es inequívoco para el reprocesador, y los elementos ya confirmados no se
duplican gracias a la deduplicación por `external_message_id` y por `event_key`.

Un elemento defectuoso no arrastra a los demás: se hace `rollback` de ese ítem y se
continúa con el siguiente. No se usan SAVEPOINTs (se comportan distinto en SQLite y
PostgreSQL). No se introdujeron Redis, Celery, Kafka ni servicios externos.

Estados de `processing_status`:

| Estado | Significado |
|---|---|
| `processed` | Hubo al menos un elemento manejado (creado o deduplicado) |
| `ignored` | Nada aplicable: objeto/`field`/tipo no soportado, línea desconocida o inactiva, estado de un mensaje que no conocemos |
| `failed` | Hubo errores, **o** el envelope no se pudo leer |

Un envelope ilegible (un tipo distinto del esperado, no un campo nuevo) se marca
`failed` y **no** `ignored`: `ignored` significa "correctamente no aplicable" y dejaría
el evento fuera del radar del reprocesador con un diagnóstico falso.

`last_error_safe` guarda el error cuando lo hay; si no hubo errores pero sí elementos
descartados, guarda los motivos con el prefijo explícito **`skipped:`**. Así un evento
`processed` con un elemento ignorado deja traza sin parecer fallado, y el reprocesador
sabe qué quedó afuera aunque el `raw_payload` ya se haya purgado.

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

> **`bsuid`: `NOT_IMPLEMENTED`.** La arquitectura §4.4 prevé tres tipos de
> identificador (`wa_id`, `phone_e164`, `bsuid`) pero el payload de webhook de Cloud
> API **no entrega `bsuid`**: aparece recién en escenarios de Coexistence / BSP. No se
> inventa el dato ni se agrega columna alguna: el tipo ya está soportado por el modelo
> (`identifier_type` es String) y se completará cuando exista una fuente real. **Debe
> resolverse antes de habilitar Coexistence** (etapa 1J), porque ahí un mismo contacto
> puede llegar identificado por `bsuid` y quedaría duplicado.

**Conversaciones.** Una por `(línea, contacto)` — el modelo tiene
`unique(line_id, contact_id)`:

```text
conversation_history_model=single_reopenable_thread_per_line_and_contact
```

Un mensaje entrante sobre un hilo cerrado lo **reabre**
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
contenido del mensaje, **identificadores externos completos** (`wamid`), tokens,
secretos ni la firma. Para correlacionar se usan:

| Dato | En el log |
|---|---|
| Registros propios | ID interno: `line_id`, `conversation_id`, `contact_id`, `message_id` |
| `event_key` (ya es un hash) | Prefijo truncado: `sha256:60e91a0f6eff…` |
| Teléfono / `wa_id` / `phone_number_id` | Enmascarado: `***0000` |
| `wamid` y otros ids externos | Huella no reversible: `ext:9f2a1c7b04` (`mask_external_id`) |

> Para los ids externos **no alcanza truncar**: un `wamid` más corto que el largo de
> truncado quedaría completo en el log. Por eso se emite un prefijo del sha256, que
> correlaciona dos apariciones del mismo id sin exponerlo nunca entero.

> **Regla dura del módulo: no se usa `logger.exception` en el camino del webhook.** El
> traceback de un error de SQLAlchemy incluye `[SQL: …]` y `[parameters: …]`, es decir
> la sentencia con los valores bindeados: texto del mensaje, `wa_id`, nombre de perfil
> y, en el INSERT del evento, el payload crudo entero. Todo error de base de datos se
> logea con `safe_error(exc)`, que además recorta el `DETAIL:` de PostgreSQL (que trae
> la fila conflictiva) antes de persistirlo en `last_error_safe`.

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

## 13. Condiciones bloqueantes para producción

Estas condiciones surgen de la revisión técnica de la etapa (código real contra
PostgreSQL 17 efímero) y son **bloqueantes**: no son recomendaciones.

```text
META_CONNECTION_BLOCKED_UNTIL_REPROCESSOR=yes
RAW_PAYLOAD_PURGE_REQUIRED_BEFORE_PRODUCTION_TRAFFIC=yes
```

### 13.1 Reproceso de eventos `failed`

**No conectar un número real hasta implementar el mecanismo de reproceso de eventos
`failed`.**

Motivo verificado: si el procesamiento de un evento falla, el evento queda almacenado
con `processing_status='failed'`, su `raw_payload` y `attempt_count`, pero **el
reintento del mismo webhook por parte de Meta NO lo reprocesa**: la deduplicación por
`event_key` lo reconoce como duplicado y responde 200.

```text
duplicate_failed_event_reprocessed=no
```

Es correcto para la idempotencia y aceptable mientras no haya tráfico real, pero
significa que hoy **la única vía de recuperación es el procesador persistente de la
etapa 1E**. Sin él, un mensaje entrante que falle se pierde de la bandeja.

### 13.2 Purga del `raw_payload`

`raw_payload_expires_at` se fija a 30 días, pero **no existe todavía el barrido que
borra los payloads vencidos**. El payload crudo contiene datos personales (teléfono,
nombre de perfil y texto del mensaje), así que la purga debe existir **antes** de
recibir tráfico productivo.

### 13.3 Desviación registrada respecto de la arquitectura §7

La arquitectura pide "persistencia rápida del evento y respuesta HTTP inmediata" con
**procesamiento desacoplado de la respuesta HTTP**. Esta etapa persiste el evento y
**procesa de forma síncrona dentro del request**, porque el desacople real es
justamente el procesador persistente de 1E (y la arquitectura §7 prohíbe apoyarse solo
en `BackgroundTasks`). Consecuencia operativa: Meta corta el webhook a los pocos
segundos, así que un evento con muchos elementos podría agotar ese margen.

**Esta desviación requiere aprobación explícita** (o bien actualizar primero el
documento de arquitectura, que es el normativo) **antes de conectar un número real**.

## 14. Limitaciones de esta etapa

- No hay conexión con Meta, ni envío de mensajes, ni plantillas, ni media.
- No hay procesador persistente de reintentos: los eventos en `failed` quedan
  almacenados y esperan la etapa siguiente (1E) para reprocesarse.
- No hay endpoints de bandeja, ni asignación, ni lectura, ni polling/SSE (frontend
  intacto).
- No hay conversión automática a lead ni asignación automática de vendedor.
- No hay purga automática del `raw_payload` vencido: solo se marca
  `raw_payload_expires_at` (30 días).
- No se cargaron líneas productivas ni se configuró nada en el panel de Meta.
- El estado `processing` de la arquitectura §5 no se usa: no hay *claim* del evento
  antes de procesarlo. El reprocesador de 1E lo va a necesitar para que dos réplicas no
  tomen el mismo evento.
- `bsuid` no se persiste todavía (ver §8).

## 15. Compatibilidad PostgreSQL / SQLite

La suite corre sobre SQLite en memoria, que **no** valida los largos de `VARCHAR`, ni
rechaza el carácter NUL, ni aborta la transacción tras un error. Por eso la revisión de
esta etapa se ejecutó además contra un **PostgreSQL 17 efímero** creado con
`alembic upgrade head`, con validación por SQL y concurrencia real por threads. De ahí
salieron correcciones que ningún test con SQLite podía detectar:

| Diferencia | Qué pasaba | Cómo se resolvió |
|---|---|---|
| Largos de `VARCHAR` (22001) | Un `profile_name`, `wa_id`, `wamid` o `context.id` de más de 255 caracteres abortaba el INSERT y perdía el mensaje | El normalizador trunca lo cosmético y descarta como no soportado lo que no se puede truncar sin romper identidad/idempotencia |
| `jsonb` rechaza el caracter NUL | Un payload con NUL devolvía 500 sin almacenar el evento: Meta lo reintentaba indefinidamente | Se guarda una copia sin NUL; el hash se sigue calculando sobre el payload original |
| Unicidad bajo concurrencia | Dos entregas simultáneas de un contacto nuevo chocaban en `uq_whatsapp_contact_identifiers_value` y un mensaje se perdía | `_process_message` reintenta una vez tras `IntegrityError` y reusa lo que la otra transacción confirmó |
| Errores con sentencia y parámetros | El traceback de SQLAlchemy incluye el SQL y los valores bindeados (texto del mensaje, teléfono, nombre) | No se usa `logger.exception` en este módulo y `safe_error` recorta `[SQL:`, `[parameters:` y `DETAIL:` |
| Surrogates sueltos (U+D800–U+DFFF) | `json.loads` los acepta pero UTF-8 no los puede codificar: el hash canónico lanzaba `UnicodeEncodeError` (que no es `UnicodeDecodeError`) y escapaba como 500 en bucle | El hash usa `ensure_ascii=True`, el saneado los quita junto con el NUL, y el router captura `ValueError` → 400 |
| `event_type` sin sanear | El `field` del payload iba crudo a `VARCHAR(64)`: un NUL ahí rompía el INSERT del evento aunque el `raw_payload` estuviera limpio | Se sanea `field` y `object` en el normalizador |

### 15.1 Comportamientos verificados que NO son defectos

Salieron de la revisión y quedan documentados para no volver a auditarlos a ciegas:

- **`Content-Length` menor que el cuerpo real**: la aplicación no compara ambos; el
  servidor ASGI (uvicorn/h11) trunca el cuerpo al `Content-Length` declarado antes de
  que el endpoint lo vea, así que la firma no valida y se responde 403. Un
  `Content-Length` inválido o negativo tampoco llega a la aplicación.
- **Corte de conexión a mitad del cuerpo**: se captura `ClientDisconnect` y se responde
  400. No se persiste nada y la sesión queda sana. Sin la captura, la excepción llegaba
  al handler global de `main.py`, que la logea con traceback completo: ruido de logs
  provocable de forma anónima y previa a la validación de firma.
- **Estado de un mensaje de otra línea**: `_process_status` localiza el mensaje por
  `wamid` sin validar que pertenezca a la línea del webhook. Los `wamid` son únicos a
  nivel global y los emite Meta, así que no hay ambigüedad posible; queda anotado por
  si alguna vez se admiten proveedores distintos.
- **Payloads degenerados** (`entry` vacío, sin `changes`, `value` nulo, listas nulas,
  `contacts[]` repetidos, envelope que no es un objeto): todos responden 200, quedan
  registrados y no producen escrituras comerciales.

### 15.2 Riesgos residuales conocidos

- **`main.py` usa `logger.exception` en su handler global** (línea 57). Este módulo ya
  no deja escapar excepciones, pero la regla de redacción vale solo mientras eso siga
  siendo cierto. El refuerzo global sería `hide_parameters=True` en el engine de
  `app/database.py`; **afecta a toda la aplicación**, así que requiere aprobación
  aparte y no se aplicó en esta etapa.
- **Validación del envelope todo-o-nada**: Pydantic valida el payload completo, así que
  un tipo inesperado en un solo elemento invalida el webhook entero (queda `failed`,
  revisable). La validación por elemento —para que un `messages[]` roto no arrastre a
  los `statuses[]` del mismo `change`— corresponde a la etapa del reprocesador.
- **Reintento amplio ante `IntegrityError`**: un conflicto no transitorio reejecuta una
  vez la resolución de contacto y conversación antes de fallar. Está acotado (un solo
  reintento) pero podría condicionarse al nombre de la constraint.
- **Los estados no se acotan a la línea**: `_process_status` busca el mensaje por
  `wamid` sin filtrar por línea (ver §15.1).

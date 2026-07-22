# UNPO — Reprocesamiento de eventos y retención de payloads (Etapa 1D)

> Capa operativa que resuelve las dos condiciones bloqueantes de 1C: reprocesar
> eventos que quedaron en `failed`/`pending`/`processing` y purgar el `raw_payload`
> vencido. Continúa a [`unpo-whatsapp-webhook-foundation.md`](./unpo-whatsapp-webhook-foundation.md).
>
> **Alcance:** solo comandos de mantenimiento locales. Esta etapa **no** conecta Meta,
> **no** conecta números, **no** envía mensajes, **no** programa cron en Render, **no**
> despliega, **no** toca frontend ni NORA.

```text
REPROCESSOR_IMPLEMENTED=yes
RAW_PAYLOAD_PURGE_COMMAND_IMPLEMENTED=yes
PRODUCTION_SCHEDULING_CONFIGURED=no
META_CONNECTION_BLOCKED_UNTIL_REPROCESSOR=yes
RAW_PAYLOAD_PURGE_REQUIRED_BEFORE_PRODUCTION_TRAFFIC=yes
```

Los dos últimos marcadores siguen vigentes: el código de 1D **existe pero todavía no
está desplegado ni programado**, así que Meta sigue bloqueado hasta que el cron real
esté corriendo en producción.

## 1. Migración (aprobada)

Revisión Alembic `b1e9d4c7f0a2` (`down_revision = efa066dfdf30`), **aditiva** sobre
`whatsapp_webhook_events`:

| Columna | Tipo | Uso |
|---|---|---|
| `processing_started_at` | `timestamptz` NULL | inicio del lease; detecta `processing` atascados |
| `next_retry_at` | `timestamptz` NULL | elegibilidad + backoff; evita reintentar poison pills en cada corrida |
| `locked_by` | `varchar(64)` NULL | trazabilidad del worker (**no** sustituye el lock de PostgreSQL) |

Índices parciales (PostgreSQL; en SQLite se crean completos, equivalentes para tests):

- `ix_whatsapp_webhook_events_processing_lease` — `WHERE processing_status = 'processing'`, por `processing_started_at`.
- `ix_whatsapp_webhook_events_retry_eligible` — `WHERE processing_status IN ('failed','pending')`, por `(next_retry_at, received_at)`.

Sin `NOT NULL` sin default, sin DML sobre filas existentes, sin tocar tablas
comerciales ni las otras `whatsapp_*`. `alembic check` confirma que modelo y migración
coinciden (sin drift). Alembic head nuevo: **`b1e9d4c7f0a2`**.

## 2. Por qué hacía falta la migración

El `processor.process_event` de 1C **commitea internamente** por cada elemento, así que
un `SELECT ... FOR UPDATE SKIP LOCKED` no puede mantener el row lock durante todo el
procesamiento. Para garantizar "cada evento se reclama una sola vez" bajo concurrencia,
el reclamo marca el evento como `processing` (estado no elegible) en una transacción
corta. Si el worker cae entre el reclamo y el cierre, el evento queda en `processing`;
recuperarlo requiere distinguir "procesándose ahora" de "colgado", lo que exige el
timestamp de lease `processing_started_at`. Sin ese campo no había forma segura, y
`received_at`/`created_at` no sirven como lease.

## 3. Estrategia de claim (arquitectura)

1. **Reclamo** (transacción corta): `SELECT ... FOR UPDATE SKIP LOCKED` de los eventos
   elegibles (limitado por batch), y en la misma transacción `UPDATE` a
   `processing_status='processing'`, `processing_started_at=now`, `locked_by=worker`,
   `attempt_count += 1`; commit. Dos workers concurrentes nunca ven las mismas filas
   (el segundo las saltea con `SKIP LOCKED`).
2. **Procesamiento**: cada evento reclamado se procesa en **su propia transacción**,
   reutilizando `process_event` (misma lógica de contactos/identificadores/
   conversaciones/mensajes/estados; sin lógica paralela).
3. **Cierre**: se marca el resultado y se libera el lease.

En SQLite `SKIP LOCKED` se ignora; la concurrencia **real** se valida en PostgreSQL 17.

## 4. Elegibilidad y recuperación de leases

Parámetros configurables (variables de entorno; los defaults son **seguros para
desarrollo**, se ajustan por entorno al programar el cron):

| Variable | Default dev | Uso |
|---|---|---|
| `WHATSAPP_REPROCESS_LEASE_SECONDS` | 300 | lease del `processing`; también "gracia" del `pending` |
| `WHATSAPP_REPROCESS_BATCH_SIZE` | 100 | tamaño del lote |
| `WHATSAPP_REPROCESS_MAX_ATTEMPTS` | 8 | 1 intento del webhook + hasta 7 reintentos |

**Elegible** para reclamo (con `raw_payload` presente salvo la rama de `processing`):

- `failed` con `attempt_count < max` y (`next_retry_at IS NULL` o `<= now`);
- `pending` con `attempt_count < max` y más viejo que el lease (`received_at <= now - lease`);
- `processing` con `processing_started_at <= now - lease` (**atascado**; sin filtro de
  payload ni de intentos, para poder cerrarlo).

**No elegible**: `processed`, `ignored`, `processing` con lease vigente, `failed` sin
payload (terminal), `next_retry_at` futuro, `attempt_count >= max` (exhausted).

Un `processing` atascado se re-reclama reemplazando `locked_by` y `processing_started_at`
e incrementando `attempt_count`. **Nunca** se usa `received_at` como lease.

## 5. Backoff y poison pills

Backoff determinístico, centralizado (`config.backoff_seconds`), por número de intento
que falló, con tope:

```text
intento 1 → 1 min      intento 2 → 5 min     intento 3 → 15 min
intento 4 → 1 h        intento 5+ → 6 h  (tope)
```

Al **fallar** un evento: `processing_status='failed'`, `processing_started_at=NULL`,
`locked_by=NULL`, `next_retry_at = now + backoff(attempt_count)`, `last_error_safe` =
error sanitizado.

Al alcanzar `MAX_ATTEMPTS` (**exhausted**): queda `failed`, `next_retry_at=NULL` (no se
reintenta más, no se elimina, no se inventa un estado nuevo). Se identifica por
`attempt_count` y se cuenta como `exhausted` en la salida. Un poison pill **no** bloquea
al resto del lote: se marca y se continúa.

## 6. Éxito

`processing_status='processed'` o `'ignored'` según el resultado real; `processed_at=now`;
`processing_started_at`, `locked_by`, `next_retry_at` en NULL; `last_error_safe=NULL`
(en `ignored` se conserva el resumen `skipped:...` de motivos, como en 1C). Se conservan
`event_key`, `payload_hash`, `received_at`, `attempt_count` y el `raw_payload` hasta su
expiración. No se duplican contactos, mensajes, conversaciones ni estados (idempotencia
del procesador de 1C).

## 7. Evento sin payload

Un evento cuyo `raw_payload` es NULL no puede reprocesarse: no se llama a `process_event`,
se cierra como `failed` con `next_retry_at=NULL`, se conserva `attempt_count`, se guarda
el motivo sanitizado `payload_missing` y se cuenta en `payload_missing` **y** `exhausted`.
Como queda `failed` sin payload, deja de ser elegible: **no genera bucle**.

## 8. Purga de `raw_payload`

Elegible: `raw_payload IS NOT NULL AND raw_payload_expires_at <= now`. Acción: `raw_payload
= NULL` (SQL NULL real, vía `null()`; asignar `None` a una columna JSONB guardaría el
literal `'null'`). **Nunca borra la fila** y preserva todas las demás columnas
(`event_key`, `payload_hash`, `processing_status`, `attempt_count`, lease, timestamps,
`last_error_safe`). Idempotente: una segunda corrida no cambia nada. Por lotes
(`--limit`): correr de nuevo purga el resto.

> **Protección:** la purga **no** toca eventos en `processing` aunque hayan vencido —
> podrían estar reprocesándose en ese momento y necesitan su payload; su lease se
> resolverá antes.

## 9. Comandos

```bash
python -m app.jobs.whatsapp_maintenance reprocess --limit 100
python -m app.jobs.whatsapp_maintenance purge --limit 500
```

Opciones: `reprocess [--limit N] [--lease-seconds S] [--worker-id ID]`,
`purge [--limit N]`. Los rangos se validan (`--limit` 1..10000, `--lease-seconds`
1..86400); fuera de rango → **exit 2** (error de uso). El `--worker-id` por defecto es
un id aleatorio corto (`wrk-<hex>`) sin hostname, email ni usuario del sistema; si se
provee, se sanea (solo `[A-Za-z0-9._-]`, máx. 64).

Códigos de salida: **0** si el lote operó bien (aunque eventos individuales hayan
fallado); **1** ante fallo operacional del lote o de la base; **2** por argumentos
inválidos.

Salida (solo enteros, sin payloads/teléfonos/nombres/wa_id/wamid/texto/SQL):

```text
WHATSAPP_REPROCESS_RESULT          WHATSAPP_PURGE_RESULT
claimed=<n>                        eligible=<n>
processed=<n>                      purged=<n>
ignored=<n>                        remaining=<n>
failed=<n>
skipped=<n>
payload_missing=<n>
exhausted=<n>
```

## 10. No tareas de fondo en FastAPI

Estos comandos se ejecutan como proceso/cron **separado**, NUNCA como tarea de fondo del
web (`asyncio.create_task`, loops, threads residentes, scheduler en memoria,
`BackgroundTasks`): Render puede reiniciar o escalar el servicio web y duplicar el
trabajo. En esta etapa solo se implementó el comando y se documentó su programación.

## 11. Propuesta de programación en Render (sin ejecutar)

**No configurada** (`PRODUCTION_SCHEDULING_CONFIGURED=no`). Propuesta para cuando se
autorice, como Cron Job / proceso separado (no asumir que Render Cron está en el plan
contratado):

```text
reprocessor
  frecuencia sugerida : cada 5 minutos
  comando             : python -m app.jobs.whatsapp_maintenance reprocess --limit 100
  timeout             : 2–3 min (el lote es rápido; sin llamadas externas)
  batch size          : 100 (WHATSAPP_REPROCESS_BATCH_SIZE)
  concurrencia        : FOR UPDATE SKIP LOCKED + lease → seguro con solapamiento

purge
  frecuencia sugerida : una vez por día
  comando             : python -m app.jobs.whatsapp_maintenance purge --limit 500
  timeout             : 5 min
  batch size          : 500
```

## 12. Métricas recomendadas (futuro)

`claimed`, `processed`, `failed`, `exhausted`, `payload_missing` por corrida;
profundidad de la cola (`count` por `processing_status`); antigüedad del `failed` más
viejo elegible; eventos en `processing` con lease vencido (indicador de crashes);
`eligible`/`remaining` de la purga.

## 13. Validación

Migración (PostgreSQL 17 efímero): `upgrade`/`current`/`heads`/`check`/`downgrade`/
`re-upgrade` PASS; columnas e índices parciales aparecen y desaparecen; 10 tablas
WhatsApp + 18 comerciales intactas; sin drift.

Servicio (PostgreSQL 17 real): reproceso, recuperación de lease atascado, backoff
persistido, max attempts→exhausted, payload_missing sin bucle, purga (con protección de
`processing`), **concurrencia real** (conexiones separadas + dos procesos CLI reales:
cada evento reclamado una sola vez, sin mensajes duplicados, sin transacciones
abortadas) y recuperación de sesión tras `IntegrityError`. Suite: 52 tests de recovery;
260 en el backend completo.

## Cómo correr los tests

```bash
docker run --rm -v "$PWD/backend:/app" -w /app --entrypoint python \
  unpo-website-backend:latest -m unittest tests.test_whatsapp_recovery
```

La concurrencia real y la migración se validan sobre un PostgreSQL 17 efímero
(`alembic upgrade head`, nunca `create_all`), no en la suite SQLite.

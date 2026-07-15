# Runbook — Adopción de la baseline de Alembic (UNPO)

**Baseline revision:** `71e9e987f7d2` (`down_revision = None`) — archivo:
`backend/alembic/versions/71e9e987f7d2_unpo_schema_baseline.py`.

**Regla de oro (leer primero):**

> La baseline **NUNCA** se ejecuta como `alembic upgrade` sobre la base productiva
> existente (crearía tablas que ya existen y podría dañar datos). Producción **solo
> adopta el revision ID de la baseline mediante `alembic stamp --purge 71e9e987f7d2`**,
> que reemplaza el valor de `alembic_version` **sin ejecutar DDL**.

**Contexto (verificado 2026-07-14):** la base productiva es **Supabase PostgreSQL 17.6**;
el schema `public` contiene solo las 18 tablas UNPO + `alembic_version`. `alembic_version`
productivo = `c9e8340fc9d6`. Drift prod↔modelo = menor (5 `DEFAULT now()`, ya incorporados
a la baseline). Alembic está restringido a `public` (ver `backend/alembic/env.py`).

> Este runbook **describe** los pasos. **No ejecutar nada de esto en esta etapa.**

---

## Validación real sobre copia productiva — Etapa 0B-2.4B

Ejecutada el 2026-07-15 sobre una **copia restaurada** de producción en PostgreSQL 17
efímero y descartable (nunca contra Supabase productivo). Datos técnicos agregados (sin
nombres, teléfonos, emails ni contenido de filas):

| Ítem | Valor |
|---|---|
| Dump | `pg_dump` custom, schema `public` |
| Cliente / restore PostgreSQL | 17 |
| Revision PRE | `c9e8340fc9d6` |
| Revision POST | `71e9e987f7d2` |
| Tablas / Columnas / Constraints / Índices / Secuencias / Enums | 18 / 144 / 31 / 47 / 16 / 8 |
| Resultado | **ADOPTION_VALIDATION_PASSED** |

Permanecieron **idénticos** (PRE == POST): hash del esquema, hash de datos (excluyendo
`public.alembic_version`), conteos de filas, valores de secuencias, valores de enums y
defaults. **El único cambio fue** `public.alembic_version: c9e8340fc9d6 → 71e9e987f7d2`.

---

## 12.1 — Validación sobre una COPIA restaurada (obligatoria antes de prod)

1. **Restaurar** el último backup productivo en un PostgreSQL **aislado** (no Supabase de
   prod, no Ripoll, no local persistente). Puede ser un contenedor efímero o una instancia
   dedicada. La copia debe tener los datos reales.
   > ⚠️ El dump custom `--schema=public` **recrea** el schema `public`. En la base
   > **efímera y descartable** de validación, antes de `pg_restore` ejecutar:
   > ```sql
   > DROP SCHEMA IF EXISTS public CASCADE;
   > ```
   > **Este `DROP SCHEMA` se usa exclusivamente sobre la base efímera y descartable de
   > validación. Nunca debe ejecutarse contra Supabase productivo.** Alternativa equivalente:
   > `pg_restore --clean --if-exists`. (Procedimiento validado en 0B-2.4B: `DROP SCHEMA` +
   > `pg_restore --exit-on-error --no-owner --no-privileges`.)
2. **Snapshot previo** del esquema y métricas de la copia:
   - `pg_dump --schema-only -n public > pre_schema.sql`
   - conteos de filas por tabla (`pg_stat_user_tables` o `count(*)` acotado).
   - `psql -Atc "select version_num from alembic_version;"` → debe ser **`c9e8340fc9d6`**.
3. **Config de Alembic:** usar la de esta rama (`env.py` con scope `public`,
   `version_table_schema="public"`). Exportar `DATABASE_URL` apuntando a la **copia** y,
   como la guarda anti-Supabase detecta hosts `*.supabase.*`, definir explícitamente
   `ALEMBIC_ALLOW_SUPABASE=true` **solo si la copia está en Supabase** (idealmente la copia
   NO es Supabase, así ni hace falta).
4. **Adoptar por stamp (sin DDL):**
   ```bash
   alembic stamp --purge 71e9e987f7d2
   ```
   `--purge` limpia la tabla `alembic_version` antes de escribir la baseline (borra el
   `c9e8340fc9d6` viejo y deja solo la baseline). **No** ejecuta `CREATE/ALTER/DROP`.
5. **Confirmar:**
   - `select version_num from alembic_version;` → solo **`71e9e987f7d2`**.
   - `pg_dump --schema-only -n public > post_schema.sql` y `diff pre_schema.sql post_schema.sql`
     → **sin diferencias** (salvo, si acaso, el contenido de `alembic_version`).
   - conteos de filas **idénticos** al snapshot previo (no se tocaron datos).
   - constraints, FKs, índices y enums iguales.
6. **Arrancar el backend** contra la copia y correr **pruebas funcionales** (login, listar
   leads, cerrar venta, etc.).
7. **Verificar que no hay drift** (esquema == modelo) con **`alembic check`** — no crea
   archivos ni revisiones temporales:
   ```bash
   alembic check   # esperado: "No new upgrade operations detected."
   ```
   Si detecta cambios, **detenerse** y analizar (drift no contemplado).
8. Recién con 1–7 en verde, planificar producción.

---

## 12.2 — Producción (DESCRIBIR, no ejecutar en esta etapa)

**Mecanismo de ejecución del `stamp`:** puede correrse **desde el Shell del backend de
Render** o **desde un contenedor backend local** correspondiente al commit desplegado,
conectado mediante la `DATABASE_URL` productiva autorizada. El Shell de Render **no** es
obligatorio. En ambos casos:
```bash
DATABASE_URL="<PRODUCTION_DATABASE_URL>" \
ALEMBIC_ALLOW_SUPABASE=true \
alembic stamp --purge 71e9e987f7d2
```
- `ALEMBIC_ALLOW_SUPABASE=true` se pasa **únicamente al proceso/comando**; **no** debe
  guardarse como variable persistente del servicio en Render.
- El código utilizado debe **contener** la baseline `71e9e987f7d2` (deploy de `763b7c5` o
  posterior); desde un deploy sin la baseline el comando fallaría ("Can't locate revision").
- **Nunca** ejecutar `alembic upgrade head` sobre la base existente.

Precondiciones y pasos (todos con aprobación explícita y ventana coordinada):

1. **Backup verificado** e inmediatamente restaurable (probar la restauración antes).
2. **Ventana controlada** de baja actividad; idealmente el backend en pausa o read-only
   durante el `stamp` (aunque `stamp` no bloquea datos, evita escrituras concurrentes en
   `alembic_version`).
3. **Conexión:** usar la conexión **directa** de Supabase o el **pooler en modo `session`**.
   **NUNCA** el pooler en modo `transaction` (rompe sentencias multi-paso / estado de sesión).
4. **Verificación de identidad** (sin imprimir credenciales): `current_database()`,
   presencia de `public.leads/products/users`, y que el host es el de UNPO (no Ripoll).
   Definir `ALEMBIC_ALLOW_SUPABASE=true` explícitamente para habilitar Alembic contra el
   host Supabase (la guarda de `env.py` lo exige a propósito).
5. **Snapshot previo:** `alembic_version` (debe ser `c9e8340fc9d6`), `pg_dump --schema-only
   -n public`, conteos de filas.
6. **Adopción:** `alembic stamp --purge 71e9e987f7d2` — **sin DDL**.
7. **Snapshot posterior:** `alembic_version` == `71e9e987f7d2`; esquema idéntico al previo;
   filas idénticas.
8. **Smoke tests** del backend contra producción.
9. **Plan de reversión** (si algo saliera mal): como durante la adopción **solo se ejecutó
   `stamp`** (cero DDL), revertir = restaurar el valor previo de `alembic_version`
   (`c9e8340fc9d6`). ⚠️ **NO** sirve `alembic stamp --purge c9e8340fc9d6` desde la rama de la
   baseline: esa revisión fue archivada y ya no está en la ruta activa. Ver la sección
   **«Rollback»** más abajo (release anterior o SQL de emergencia).
10. **Monitoreo** post-adopción (errores del backend, latencia, logs).

> Reafirmación: **la baseline nunca se ejecuta como `upgrade` sobre producción existente.
> Producción solamente adopta su revision ID mediante `alembic stamp --purge`.**

---

## Rollback (reversión de la adopción)

Como la adopción **solo ejecuta `stamp`** (nunca DDL), el esquema y los datos NO cambian:
revertir es únicamente restaurar el bookkeeping de Alembic a `c9e8340fc9d6`.

> ⚠️ **No** se puede correr `alembic stamp --purge c9e8340fc9d6` desde la rama de la baseline:
> `c9e8340fc9d6` está **archivada** en `backend/alembic/legacy_versions/` y no forma parte de
> `backend/alembic/versions/`, así que Alembic falla con "Can't locate revision". Verificado en
> PostgreSQL 17 efímero (Etapa 0B-2.3 — correcciones).

### Opción principal — volver al release anterior

1. Detener nuevas operaciones de migración.
2. Re-desplegar **temporalmente** el commit **anterior** a la baseline en `main`:
   **`e417906`** (último commit de `main` antes de la baseline, donde la cadena histórica y
   la revisión `c9e8340fc9d6` todavía existen en `backend/alembic/versions/`).
   > ⚠️ **No** usar el hash de seguridad **obsoleto** previo a la corrección de identidad:
   > se reemplazó por `c521ac7`, que quedó mergeado en `main` como `e417906`.
3. Confirmar que ese release contiene la cadena histórica y `c9e8340fc9d6` en
   `backend/alembic/versions/`.
4. Desde ese release, revertir el bookkeeping:
   ```bash
   alembic stamp --purge c9e8340fc9d6
   ```
5. Verificar **una sola fila** en `public.alembic_version`:
   ```sql
   SELECT version_num FROM public.alembic_version;   -- esperado: c9e8340fc9d6 (1 fila)
   ```
6. Revalidar el servicio (login, leads, productos, ventas, logs).

### Opción de emergencia — restaurar el bookkeeping por SQL (solo con autorización)

Si no fuera viable re-desplegar `e417906`, y **solo** después de verificar la identidad de la
base y que **`public.alembic_version` contiene una única fila**, dentro de una ventana
controlada y con backup disponible:
```sql
BEGIN;
DELETE FROM public.alembic_version;
INSERT INTO public.alembic_version (version_num) VALUES ('c9e8340fc9d6');
COMMIT;
```
> ⚠️ El SQL de emergencia **solo modifica el bookkeeping de Alembic** (la tabla
> `public.alembic_version`); no toca tablas comerciales ni el esquema. **Antes de ejecutarlo
> debe comprobarse que `public.alembic_version` contiene una única fila.**

- Solo modifica el **bookkeeping** de Alembic; **no** toca tablas comerciales.
- No revierte DDL, porque durante la adopción solo se ejecutó `stamp`.
- **No** se crea una revisión stub para `c9e8340fc9d6` ni se devuelven las migraciones
  históricas a `versions/`.
- **No se ejecuta en esta etapa.**

---

## Después de la adopción (etapas siguientes, fuera de este runbook)

- Recién con la baseline adoptada y validada, se podrá **retirar
  `Base.metadata.create_all()` de `backend/app/main.py`** (etapa 0B-2.x independiente),
  y correr migraciones en el deploy.
- Las tablas de **WhatsApp** se agregan como migraciones normales que cuelgan de
  `71e9e987f7d2` (con `String` en vez de enums nativos, para evitar `ALTER TYPE`).

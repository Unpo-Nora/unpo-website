# Migraciones históricas archivadas (NO son la ruta activa de Alembic)

Estas 6 revisiones fueron **archivadas** el **2026-07-14** al introducir una nueva
**baseline raíz** de Alembic (ver `backend/alembic/versions/`). Están fuera de la ruta
activa: Alembic **no** las ve (solo lee `alembic/versions/`). Se conservan como
referencia histórica y **no deben volver a colocarse** en `versions/`.

## Motivo del archivado

La cadena histórica estaba **rota e incompleta**, y por lo tanto no permitía reconstruir
la base desde cero ni servir de base confiable para migraciones futuras (p. ej. las tablas
de WhatsApp). En concreto:

- `1d74bcbcf943_initial_migration.py` está **vacía** (`upgrade`/`downgrade` = `pass`): la
  tabla base `leads`/`products`/etc. **nunca** se creó vía Alembic.
- Las migraciones siguientes hacen `add_column`/`alter_column` sobre tablas que Alembic
  nunca creó → **fallan en una base vacía**.
- `d88928b773ad_add_saleorders_and_orderitems.py` tiene **nombre engañoso**: NO crea
  `sale_orders`/`order_items`; solo agrega columnas de facturación a `leads`.
- `sale_orders` y `order_items` **no tienen `create_table`** en ninguna revisión.
- El esquema productivo real fue construido efectivamente por
  `Base.metadata.create_all()` (`backend/app/main.py:16`), no por esta cadena.

## DAG histórico (dos heads)

```
1d74bcbcf943  (base, VACÍA)
└── d50c8f471238  (ALTER leads: +10 cols; drop name/company_name/interest_data)
    └── a7da328604d3  (ALTER products: +8 cols)     ◄── BRANCHPOINT
        ├── d88928b773ad   ◄── HEAD #1  (rama muerta; solo ALTER leads +dni_cuit/…)
        └── b8e7239fb8c5   (finanzas: CREATE 5 tablas + 6 enums; migra datos de expenses)
            └── c9e8340fc9d6   ◄── HEAD #2
```

- **Dos heads:** `c9e8340fc9d6` y `d88928b773ad` → `alembic upgrade head` fallaba con
  "Multiple head revisions".
- El enum `purchasepaymenttype` de `b8e7239fb8c5` usa los **valores** `30_DIAS`/`60_DIAS`,
  mientras que producción tiene los **nombres** `DIAS_30`/`DIAS_60` (que es lo que crea
  `create_all`). Confirma que esta migración **no** fue la fuente efectiva del esquema.

## Estado productivo previo a la baseline

Verificado el 2026-07-14 sobre la base productiva (Supabase PostgreSQL 17.6, schema
`public`):

```
alembic_version = c9e8340fc9d6      (un solo valor; HEAD #2)
```

La rama muerta `d88928b773ad` **nunca** se registró en producción.

## La nueva baseline las reemplaza

La baseline raíz en `backend/alembic/versions/` (`down_revision = None`) representa el
**esquema productivo canónico completo** (18 tablas, 8 enums, FKs, índices, y los 5
`DEFAULT now()` reales). A partir de ella cuelgan las migraciones futuras (p. ej. WhatsApp).

## Cómo se adopta producción (IMPORTANTE)

**La baseline NUNCA se ejecuta como `upgrade` sobre la base productiva existente** (crearía
tablas que ya existen y podría dañar datos). Producción **solo adopta el revision ID de la
baseline mediante `alembic stamp --purge <BASELINE_REVISION>`** (reemplaza
`c9e8340fc9d6` por la baseline sin ejecutar DDL), y **después** de validar sobre una copia
restaurada. Ver `docs/unpo-alembic-baseline-runbook.md`.

> No mover estos archivos de vuelta a `versions/`. No editarlos. No ejecutarlos.

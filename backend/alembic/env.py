from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from app.database import Base
import app.models  # noqa

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# UNPO — reconciliación de esquema (Etapa 0B-2.3)
#
# La base productiva de UNPO es Supabase: además del schema `public` (tablas UNPO)
# convive con schemas administrados por Supabase (auth, storage, realtime, vault,
# extensions, graphql, supabase_migrations, ...). Alembic debe operar EXCLUSIVAMENTE
# sobre `public` y JAMÁS tocar/reflejar esos schemas.
# ---------------------------------------------------------------------------

# La tabla de versión de Alembic vive en `public`.
VERSION_TABLE_SCHEMA = "public"

# Schemas administrados por Supabase (u otros) que NUNCA deben reflejarse ni tocarse.
SUPABASE_MANAGED_SCHEMAS = {
    "auth", "storage", "realtime", "vault", "extensions", "graphql",
    "graphql_public", "supabase_migrations", "supabase_functions",
    "pgbouncer", "cron", "net", "_realtime", "pgsodium", "pgsodium_masks",
}


def include_name(name, type_, parent_names):
    """
    Restringe autogenerate/reflexión a `public` y a las tablas conocidas por los modelos.
    - schema: solo `public` (o None = search_path).
    - table: solo tablas presentes en target_metadata + la interna `alembic_version`.
    Cualquier objeto de un schema administrado por Supabase queda excluido.
    """
    if type_ == "schema":
        return name in (None, "public")
    if type_ == "table":
        schema = (parent_names or {}).get("schema_name")
        if schema in SUPABASE_MANAGED_SCHEMAS:
            return False
        # Solo las tablas de los modelos. `alembic_version` queda EXCLUIDA a propósito
        # (la gestiona Alembic internamente); incluirla haría que autogenerate intente
        # dropearla.
        return name in set(target_metadata.tables.keys())
    return True


def _guard_against_supabase_production() -> None:
    """
    Guarda de seguridad: si `DATABASE_URL` apunta a un host de Supabase, exige una
    variable explícita `ALEMBIC_ALLOW_SUPABASE=true` para continuar. NO imprime la URL.
    Producción se adopta por `alembic stamp --purge`, NUNCA por `upgrade`.
    (Etapa 0B-2.3: se agrega la guarda, pero NO se define/usa la variable en esta etapa.)
    """
    db_url = os.getenv("DATABASE_URL", "").lower()
    if not db_url:
        raise RuntimeError("DATABASE_URL no está configurada")
    looks_supabase = ("supabase" in db_url) or ("pooler.supabase" in db_url)
    if looks_supabase and os.getenv("ALEMBIC_ALLOW_SUPABASE", "").lower() != "true":
        raise RuntimeError(
            "DATABASE_URL parece apuntar a un host de Supabase. Para correr Alembic "
            "contra Supabase, definí explícitamente ALEMBIC_ALLOW_SUPABASE=true. "
            "IMPORTANTE: producción se adopta con 'alembic stamp --purge', nunca con "
            "'alembic upgrade'."
        )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = os.getenv("DATABASE_URL")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_schemas=False,
        include_name=include_name,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        # Offline: emitir explícitamente el search_path a `public` en el SQL generado
        # (en online se fuerza vía connect_args). Nunca auth/storage/realtime/vault.
        context.execute("SET search_path TO public")
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = os.getenv("DATABASE_URL")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Forzar search_path a `public` a nivel de conexión (per-sesión, no permanente).
        connect_args={"options": "-csearch_path=public"},
    )

    # Verificación de schema activo en una conexión separada y efímera.
    with connectable.connect() as check_conn:
        current_schema = check_conn.exec_driver_sql("select current_schema()").scalar()
        if current_schema != "public":
            raise RuntimeError(
                f"Alembic exige el schema activo 'public' (current_schema={current_schema!r}). "
                "Abortando para no tocar schemas administrados por Supabase."
            )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=VERSION_TABLE_SCHEMA,
            include_schemas=False,
            include_name=include_name,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Guarda antes de ejecutar cualquier comando que corra env.py (upgrade/downgrade/
# stamp/revision --autogenerate). Los comandos file-based (heads/history/branches)
# NO ejecutan env.py y no se ven afectados.
_guard_against_supabase_production()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

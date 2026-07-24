"""
Tests estructurales del modelo de datos WhatsApp Cloud API multiagente (Etapa 1B).

Chequeos ESTÁTICOS (no conectan a ninguna base): usan la API de Alembic `ScriptDirectory`
para el árbol de revisiones, AST/regex sobre el archivo de migración, e introspección de los
modelos SQLAlchemy. La validación REAL de constraints/índices/FK se hizo aparte sobre un
PostgreSQL 17 efímero (upgrade/check/downgrade/re-upgrade). Corre sin dependencias nuevas:

    python -m unittest tests.test_whatsapp_schema -v
"""

import ast
import os
import re
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# backend/ (este archivo está en backend/tests/)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_DIR = os.path.join(BACKEND_DIR, "alembic")
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")
MIGRATION_FILE = os.path.join(VERSIONS_DIR, "efa066dfdf30_add_whatsapp_multi_agent_data_model.py")
MAIN_PY = os.path.join(BACKEND_DIR, "app", "main.py")

REVISION = "efa066dfdf30"
DOWN_REVISION = "71e9e987f7d2"
# Etapa 1D encadenó la migración de lease de reprocesamiento por encima de la de 1B.
# El head ahora es esta revisión; efa066dfdf30 sigue en la cadena con su down intacto.
RECOVERY_REVISION = "b1e9d4c7f0a2"
FK_NAME = "fk_whatsapp_conversation_reads_last_read_message_id"

WHATSAPP_TABLES = {
    "whatsapp_lines",
    "whatsapp_line_user_access",
    "whatsapp_contacts",
    "whatsapp_contact_identifiers",
    "whatsapp_conversations",
    "whatsapp_conversation_reads",
    "whatsapp_messages",
    "whatsapp_message_status_events",
    "whatsapp_webhook_events",
    "whatsapp_conversation_assignments",
}

# Tablas comerciales que la migración NO debe crear, alterar ni eliminar.
COMMERCIAL_TABLES = {"users", "leads", "products", "sale_orders", "order_items"}

# Nombres prohibidos como columnas: los secretos van SOLO a variables de entorno.
FORBIDDEN_SECRET_COLUMNS = {"access_token", "app_secret", "verify_token", "system_user_token"}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _migration_src():
    return _read(MIGRATION_FILE)


def _upgrade_downgrade_src():
    src = _migration_src()
    assert "def downgrade" in src, "La migración debe tener downgrade()"
    upgrade_src, downgrade_src = src.split("def downgrade", 1)
    return upgrade_src, downgrade_src


def _script_dir():
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg)


def _attr_name(func):
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


def _create_table_node(tree, table_name):
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and _attr_name(node.func) == "create_table"
                and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == table_name):
            return node
    return None


class WhatsAppMigrationTest(unittest.TestCase):
    """Chequeos sobre el archivo de migración efa066dfdf30."""

    def test_migration_file_exists(self):
        self.assertTrue(os.path.exists(MIGRATION_FILE), "Falta la migración efa066dfdf30")

    def test_revision_and_down_revision(self):
        script = _script_dir()
        rev = script.get_revision(REVISION)
        self.assertIsNotNone(rev, "La revisión efa066dfdf30 debe existir")
        self.assertEqual(rev.down_revision, DOWN_REVISION,
                         "down_revision debe ser la baseline 71e9e987f7d2")

    def test_single_head(self):
        # Un único head. Desde 1D el head es la migración de lease de reprocesamiento,
        # encadenada sobre 1B (efa066dfdf30 -> b1e9d4c7f0a2).
        script = _script_dir()
        heads = script.get_heads()
        self.assertEqual(heads, [RECOVERY_REVISION],
                         f"Debe haber un único head = {RECOVERY_REVISION}")

    def test_recovery_revision_chains_onto_whatsapp_baseline(self):
        script = _script_dir()
        rev = script.get_revision(RECOVERY_REVISION)
        self.assertIsNotNone(rev, "La revisión de recovery b1e9d4c7f0a2 debe existir")
        self.assertEqual(rev.down_revision, REVISION,
                         "recovery debe encadenar sobre efa066dfdf30")

    def test_creates_exactly_ten_whatsapp_tables(self):
        created = set(re.findall(r"op\.create_table\(\s*'([^']+)'", _migration_src()))
        self.assertEqual(created, WHATSAPP_TABLES,
                         f"Diferencia de tablas: {created ^ WHATSAPP_TABLES}")

    def test_does_not_create_whatsapp_media(self):
        self.assertNotIn("op.create_table('whatsapp_media'", _migration_src(),
                         "whatsapp_media NO debe crearse en esta migración")

    def test_circular_fk_resolved_explicitly(self):
        upgrade_src, downgrade_src = _upgrade_downgrade_src()
        # Se agrega por op.create_foreign_key() en upgrade y se elimina por op.drop_constraint()
        # en downgrade, ambos con el mismo nombre de constraint.
        self.assertIn("op.create_foreign_key(", upgrade_src)
        self.assertIn(FK_NAME, upgrade_src)
        self.assertIn("op.drop_constraint(", downgrade_src)
        self.assertIn(FK_NAME, downgrade_src)

    def test_no_inline_fk_to_messages_in_conversation_reads(self):
        # Dentro del create_table de whatsapp_conversation_reads NO debe haber una
        # ForeignKeyConstraint que referencie whatsapp_messages (se resuelve por ALTER aparte).
        tree = ast.parse(_migration_src())
        node = _create_table_node(tree, "whatsapp_conversation_reads")
        self.assertIsNotNone(node, "Debe existir create_table('whatsapp_conversation_reads')")
        referenced = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and _attr_name(sub.func) == "ForeignKeyConstraint":
                if len(sub.args) >= 2 and isinstance(sub.args[1], (ast.List, ast.Tuple)):
                    for el in sub.args[1].elts:
                        if isinstance(el, ast.Constant):
                            referenced.append(el.value)
        self.assertFalse(
            any("whatsapp_messages" in r for r in referenced),
            "La FK a whatsapp_messages NO debe declararse inline en conversation_reads",
        )
        # ...pero la columna last_read_message_id SÍ debe seguir estando.
        col_names = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and _attr_name(sub.func) == "Column":
                if sub.args and isinstance(sub.args[0], ast.Constant):
                    col_names.append(sub.args[0].value)
        self.assertIn("last_read_message_id", col_names)

    def test_partial_unique_indexes_on_messages(self):
        src = _migration_src()
        # (provider, external_message_id) WHERE external_message_id IS NOT NULL
        self.assertRegex(
            src,
            r"create_index\(\s*'uq_whatsapp_messages_provider_external_id'.*?"
            r"unique=True.*?postgresql_where=sa\.text\('external_message_id IS NOT NULL'\)",
        )
        # (client_request_id) WHERE client_request_id IS NOT NULL
        self.assertRegex(
            src,
            r"create_index\(\s*'uq_whatsapp_messages_client_request_id'.*?"
            r"unique=True.*?postgresql_where=sa\.text\('client_request_id IS NOT NULL'\)",
        )

    def test_payloads_use_jsonb(self):
        src = _migration_src()
        # safe_payload y raw_payload deben declararse como postgresql.JSONB en la migración.
        self.assertRegex(src, r"'safe_payload',\s*postgresql\.JSONB")
        self.assertRegex(src, r"'raw_payload',\s*postgresql\.JSONB")

    def test_states_are_string_not_native_enum(self):
        # La migración WhatsApp NO debe declarar enums PostgreSQL nativos.
        self.assertNotIn("sa.Enum(", _migration_src(),
                         "Los estados nuevos deben ser String, no sa.Enum")

    def test_no_secret_columns_in_migration(self):
        src = _migration_src()
        for name in FORBIDDEN_SECRET_COLUMNS:
            self.assertNotIn(f"'{name}'", src, f"La migración no debe tener columna {name}")

    def test_migration_does_not_touch_commercial_tables(self):
        upgrade_src, downgrade_src = _upgrade_downgrade_src()
        # upgrade es puramente aditivo: nada de drop/alter/add/drop_column.
        for forbidden in ("op.drop_table(", "op.alter_column(", "op.add_column(", "op.drop_column("):
            self.assertNotIn(forbidden, upgrade_src,
                             f"upgrade() no debe contener {forbidden}")
        # Ninguna tabla comercial se crea ni se dropea en toda la migración.
        src_nospace = _migration_src().replace(" ", "")
        for t in COMMERCIAL_TABLES:
            self.assertNotIn(f"create_table('{t}'", src_nospace)
            self.assertNotIn(f"drop_table('{t}'", src_nospace)

    def test_downgrade_only_drops_whatsapp_tables(self):
        _, downgrade_src = _upgrade_downgrade_src()
        dropped = set(re.findall(r"op\.drop_table\(\s*'([^']+)'", downgrade_src))
        self.assertEqual(dropped, WHATSAPP_TABLES,
                         "downgrade() debe dropear exactamente las 10 tablas whatsapp_*")
        # Todo drop_index / drop_constraint de downgrade apunta a tablas whatsapp_*.
        idx_tables = re.findall(r"drop_index\([^)]*table_name='([^']+)'", downgrade_src)
        con_tables = re.findall(r"drop_constraint\(\s*'[^']+'\s*,\s*'([^']+)'", downgrade_src)
        for tbl in idx_tables + con_tables:
            self.assertTrue(tbl.startswith("whatsapp_"),
                            f"downgrade() no debe tocar la tabla no-whatsapp {tbl}")


class WhatsAppModelsTest(unittest.TestCase):
    """Introspección de los modelos SQLAlchemy (app.models)."""

    @classmethod
    def setUpClass(cls):
        from app import models
        cls.models = models
        cls.metadata = models.Base.metadata

    def test_all_ten_tables_registered(self):
        for tbl in WHATSAPP_TABLES:
            self.assertIn(tbl, self.metadata.tables, f"Falta la tabla {tbl} en el metadata")

    def test_whatsapp_media_not_registered(self):
        self.assertNotIn("whatsapp_media", self.metadata.tables)

    def test_no_secret_columns_in_models(self):
        for tbl in WHATSAPP_TABLES:
            cols = set(self.metadata.tables[tbl].columns.keys())
            self.assertEqual(cols & FORBIDDEN_SECRET_COLUMNS, set(),
                             f"{tbl} no debe tener columnas de secretos")

    def test_last_read_message_id_fk(self):
        col = self.metadata.tables["whatsapp_conversation_reads"].c["last_read_message_id"]
        self.assertTrue(col.nullable, "last_read_message_id debe ser nullable")
        fks = list(col.foreign_keys)
        self.assertEqual(len(fks), 1)
        fk = fks[0]
        self.assertEqual(fk.name, FK_NAME)
        self.assertEqual(fk.ondelete, "SET NULL")
        self.assertEqual(fk.column.table.name, "whatsapp_messages")

    def test_client_request_id_is_uuid(self):
        col = self.metadata.tables["whatsapp_messages"].c["client_request_id"]
        self.assertIsInstance(col.type, sa.Uuid)

    def test_payload_columns_are_jsonb(self):
        se = self.metadata.tables["whatsapp_message_status_events"].c["safe_payload"]
        we = self.metadata.tables["whatsapp_webhook_events"].c["raw_payload"]
        self.assertIsInstance(se.type, postgresql.JSONB)
        self.assertIsInstance(we.type, postgresql.JSONB)

    def test_state_columns_are_string_not_enum(self):
        cases = [
            ("whatsapp_conversations", "status"),
            ("whatsapp_conversations", "assignment_source"),
            ("whatsapp_messages", "direction"),
            ("whatsapp_messages", "current_status"),
            ("whatsapp_messages", "origin"),
            ("whatsapp_webhook_events", "processing_status"),
            ("whatsapp_message_status_events", "status"),
        ]
        for tbl, col in cases:
            t = self.metadata.tables[tbl].c[col].type
            self.assertIsInstance(t, sa.String, f"{tbl}.{col} debe ser String")
            self.assertNotIsInstance(t, sa.Enum, f"{tbl}.{col} NO debe ser Enum nativo")

    def test_ondelete_towards_users_and_leads_is_set_null(self):
        # FKs hacia users/leads que conservan historial → SET NULL.
        set_null_cases = [
            ("whatsapp_contacts", "lead_id"),
            ("whatsapp_conversations", "lead_id"),
            ("whatsapp_conversations", "assigned_user_id"),
            ("whatsapp_messages", "sender_user_id"),
            ("whatsapp_conversation_assignments", "from_user_id"),
            ("whatsapp_conversation_assignments", "to_user_id"),
            ("whatsapp_conversation_assignments", "assigned_by_user_id"),
        ]
        for tbl, col in set_null_cases:
            fk = list(self.metadata.tables[tbl].c[col].foreign_keys)[0]
            self.assertEqual(fk.ondelete, "SET NULL", f"{tbl}.{col} debe ser SET NULL")

    def test_ondelete_module_children_cascade(self):
        cascade_cases = [
            ("whatsapp_contact_identifiers", "contact_id"),
            ("whatsapp_messages", "conversation_id"),
            ("whatsapp_message_status_events", "message_id"),
            ("whatsapp_conversation_reads", "conversation_id"),
            ("whatsapp_conversation_assignments", "conversation_id"),
            ("whatsapp_line_user_access", "line_id"),
        ]
        for tbl, col in cascade_cases:
            fk = list(self.metadata.tables[tbl].c[col].foreign_keys)[0]
            self.assertEqual(fk.ondelete, "CASCADE", f"{tbl}.{col} debe ser CASCADE")

    def test_conversation_line_and_contact_restrict(self):
        for col in ("line_id", "contact_id"):
            fk = list(self.metadata.tables["whatsapp_conversations"].c[col].foreign_keys)[0]
            self.assertEqual(fk.ondelete, "RESTRICT", f"conversations.{col} debe ser RESTRICT")

    def test_partial_unique_indexes_present_in_metadata(self):
        idx_names = {ix.name for ix in self.metadata.tables["whatsapp_messages"].indexes}
        self.assertIn("uq_whatsapp_messages_provider_external_id", idx_names)
        self.assertIn("uq_whatsapp_messages_client_request_id", idx_names)

    def test_recovery_lease_columns_present(self):
        # Etapa 1D: columnas de lease/reintento en whatsapp_webhook_events.
        cols = self.metadata.tables["whatsapp_webhook_events"].c
        for name in ("processing_started_at", "next_retry_at", "locked_by"):
            self.assertIn(name, cols, f"Falta la columna 1D {name}")
        self.assertTrue(cols["processing_started_at"].nullable)
        self.assertTrue(cols["next_retry_at"].nullable)
        self.assertTrue(cols["locked_by"].nullable)
        self.assertIsInstance(cols["processing_started_at"].type, sa.DateTime)
        self.assertIsInstance(cols["next_retry_at"].type, sa.DateTime)
        self.assertIsInstance(cols["locked_by"].type, sa.String)

    def test_recovery_partial_indexes_present(self):
        idx = {ix.name for ix in self.metadata.tables["whatsapp_webhook_events"].indexes}
        self.assertIn("ix_whatsapp_webhook_events_processing_lease", idx)
        self.assertIn("ix_whatsapp_webhook_events_retry_eligible", idx)


class StartupInvariantTest(unittest.TestCase):
    """El arranque sigue sin ejecutar DDL (Alembic es el único gestor del esquema)."""

    def test_main_does_not_call_create_all(self):
        tree = ast.parse(_read(MAIN_PY))
        create_all_calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "create_all"
        ]
        self.assertEqual(create_all_calls, [], "main.py no debe llamar create_all() en el arranque")


if __name__ == "__main__":
    unittest.main(verbosity=2)

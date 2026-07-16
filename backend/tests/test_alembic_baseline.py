"""
Tests de la baseline de reconciliación de Alembic (Etapa 0B-2.3).

Son chequeos ESTÁTICOS (no conectan a ninguna base): usan la API de alembic
`ScriptDirectory` para leer el árbol de revisiones e introspección de los modelos.
No requieren dependencias nuevas (alembic ya es dependencia). Corren con:

    python -m unittest tests.test_alembic_baseline -v
"""

import os
import re
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory

# backend/ (este archivo está en backend/tests/)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_DIR = os.path.join(BACKEND_DIR, "alembic")
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")
LEGACY_DIR = os.path.join(ALEMBIC_DIR, "legacy_versions")
RUNBOOK = os.path.join(os.path.dirname(BACKEND_DIR), "docs", "unpo-alembic-baseline-runbook.md")

EXPECTED_TABLES = {
    "brands", "capital_ivas", "categories", "employees", "expenses",
    "financial_transactions", "inventory_audit_logs", "leads", "order_items",
    "page_views", "products", "purchase_cost_details", "purchase_items",
    "purchases", "sale_orders", "settings", "suppliers", "users",
}

LEGACY_FILES = {
    "1d74bcbcf943_initial_migration.py",
    "d50c8f471238_add_detailed_leads_table.py",
    "a7da328604d3_extend_product_model.py",
    "d88928b773ad_add_saleorders_and_orderitems.py",
    "b8e7239fb8c5_add_finance_module.py",
    "c9e8340fc9d6_add_assigned_seller_phone_to_lead.py",
}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _script_dir():
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg)


def _versions_py():
    return [f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")]


def _baseline_source():
    files = _versions_py()
    assert len(files) == 1, f"Se esperaba 1 baseline en versions/, hay {files}"
    return _read(os.path.join(VERSIONS_DIR, files[0]))


class AlembicBaselineTest(unittest.TestCase):
    def test_single_active_revision_head_base(self):
        script = _script_dir()
        self.assertEqual(len(script.get_heads()), 1, "Debe haber un único head")
        self.assertEqual(len(script.get_bases()), 1, "Debe haber una única base")
        revs = list(script.walk_revisions())
        self.assertEqual(len(revs), 1, "Debe haber una única revisión activa (la baseline)")

    def test_baseline_down_revision_is_none(self):
        script = _script_dir()
        base_rev = script.get_revision(script.get_bases()[0])
        self.assertIsNone(base_rev.down_revision, "La baseline debe tener down_revision=None")
        self.assertIsNone(base_rev.branch_labels or None)

    def test_versions_dir_has_only_baseline(self):
        self.assertEqual(len(_versions_py()), 1, "versions/ debe tener solo la baseline")

    def test_historical_migrations_are_archived(self):
        legacy = set(os.listdir(LEGACY_DIR))
        for f in LEGACY_FILES:
            self.assertIn(f, legacy, f"Falta {f} en legacy_versions/")
        active = set(_versions_py())
        self.assertEqual(active & LEGACY_FILES, set(), "Ninguna migración histórica debe estar en versions/")

    def test_baseline_creates_18_tables(self):
        src = _baseline_source()
        created = set(re.findall(r"op\.create_table\(\s*'([^']+)'", src))
        self.assertEqual(created, EXPECTED_TABLES, f"Diferencia de tablas: {created ^ EXPECTED_TABLES}")

    def test_purchasepaymenttype_uses_member_names(self):
        src = _baseline_source()
        self.assertIn("DIAS_30", src)
        self.assertIn("DIAS_60", src)
        self.assertNotIn("30_DIAS", src)
        self.assertNotIn("60_DIAS", src)

    def test_downgrade_is_guarded(self):
        src = _baseline_source()
        self.assertIn("allow_destructive_baseline_downgrade", src)

    def test_env_restricts_to_public_and_excludes_supabase(self):
        env = _read(os.path.join(ALEMBIC_DIR, "env.py"))
        self.assertIn('version_table_schema', env)
        self.assertIn('"public"', env)
        self.assertIn("compare_type=True", env)
        self.assertIn("compare_server_default=True", env)
        for schema in ("auth", "storage", "realtime", "vault"):
            self.assertIn(schema, env, f"env.py debe excluir el schema {schema}")

    def test_models_declare_five_server_defaults(self):
        from app import models
        cases = [
            (models.Lead, "created_at"),
            (models.PageView, "created_at"),
            (models.SaleOrder, "created_at"),
            (models.InventoryAuditLog, "created_at"),
            (models.Expense, "date"),
        ]
        for model, col in cases:
            self.assertIsNotNone(
                model.__table__.c[col].server_default,
                f"{model.__tablename__}.{col} debe tener server_default",
            )
        # Control: estas NO deben tener server_default (no formaban parte del drift).
        self.assertIsNone(models.CapitalIva.__table__.c["created_at"].server_default)
        self.assertIsNone(models.FinancialTransaction.__table__.c["created_at"].server_default)

    def test_main_does_not_call_create_all(self):
        # El arranque productivo NO debe ejecutar create_all: Alembic es el único gestor de
        # esquema. Se analiza por AST para ignorar comentarios/strings (el comentario
        # explicativo de main.py menciona create_all a propósito).
        import ast
        tree = ast.parse(_read(os.path.join(BACKEND_DIR, "app", "main.py")))
        create_all_calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "create_all"
        ]
        self.assertEqual(create_all_calls, [], "main.py no debe llamar a create_all() en el arranque")

    def test_main_does_not_import_or_run_alembic(self):
        # El arranque no debe importar ni ejecutar Alembic automáticamente (AST evita falsos
        # positivos del comentario explicativo).
        import ast
        tree = ast.parse(_read(os.path.join(BACKEND_DIR, "app", "main.py")))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(
                        alias.name == "alembic" or alias.name.startswith("alembic."),
                        "main.py no debe importar alembic",
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertFalse(
                    node.module == "alembic" or node.module.startswith("alembic."),
                    "main.py no debe importar desde alembic",
                )

    # ---- Correcciones 0B-2.3 (offline / guardas / runbook) ----

    def test_offline_emits_set_search_path(self):
        env = _read(os.path.join(ALEMBIC_DIR, "env.py"))
        self.assertIn('context.execute("SET search_path TO public")', env,
                      "El modo offline debe emitir SET search_path TO public")

    def test_guard_rejects_empty_database_url(self):
        env = _read(os.path.join(ALEMBIC_DIR, "env.py"))
        self.assertIn("if not db_url", env)
        self.assertIn("DATABASE_URL no está configurada", env)

    def test_guard_supabase_check_is_case_insensitive(self):
        env = _read(os.path.join(ALEMBIC_DIR, "env.py"))
        self.assertIn('os.getenv("DATABASE_URL", "").lower()', env,
                      "La guarda debe normalizar la URL con .lower() (case-insensitive)")

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_rollback_via_previous_release(self):
        rb = _read(RUNBOOK)
        # El release de rollback correcto es e417906; el obsoleto 3927a3d NO debe aparecer.
        self.assertIn("e417906", rb)
        self.assertNotIn("3927a3d", rb)
        self.assertIn("c9e8340fc9d6", rb)
        self.assertIn("Can't locate", rb)

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_has_emergency_sql(self):
        rb = _read(RUNBOOK)
        self.assertIn("DELETE FROM public.alembic_version", rb)
        self.assertIn("INSERT INTO public.alembic_version", rb)

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_restore_drop_schema_only_ephemeral(self):
        rb = _read(RUNBOOK)
        self.assertIn("DROP SCHEMA IF EXISTS public CASCADE", rb)
        self.assertIn("efímera y descartable", rb)
        self.assertIn("Nunca debe ejecutarse contra Supabase productivo", rb)

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_recommends_alembic_check(self):
        self.assertIn("alembic check", _read(RUNBOOK))

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_has_validation_evidence(self):
        self.assertIn("ADOPTION_VALIDATION_PASSED", _read(RUNBOOK))

    @unittest.skipUnless(os.path.exists(RUNBOOK), "runbook fuera del contexto (docs/ no montado)")
    def test_runbook_allow_supabase_not_persistent(self):
        # No debe recomendarse persistir ALEMBIC_ALLOW_SUPABASE en Render.
        self.assertIn("variable persistente", _read(RUNBOOK))


if __name__ == "__main__":
    unittest.main(verbosity=2)

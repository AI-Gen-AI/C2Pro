"""TS-UT-PC2B2-MIGRATION-001 -- PC-2b.2 intelligence store migration (static guarantees).

Behaviour (upgrade/downgrade, RLS with a NOBYPASSRLS probe, immutability, composite-FK isolation,
idempotency, schema parity with the ORM) runs on a real PostgreSQL in
tests/integration/product_control/test_pc2b2_wbs_intelligence_store_migration_db.py and
tests/modules/integration/test_pc2b2_wbs_intelligence_store.py.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from src.wbs.adapters.persistence import intelligence_ddl

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261007_0001_pc2b2_wbs_intelligence_store.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"
TABLES = ("wbs_intelligence_runs", "wbs_intelligence_items", "wbs_intelligence_decisions")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(statements: tuple[str, ...]) -> str:
    return re.sub(r"\s+", " ", " ".join(statements))


def test_extends_the_single_chain_after_the_current_head() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261007_0001", "20261006_0003")
    children = [p.name for p in MIGRATION.parent.glob("*.py")
                if 'down_revision = "20261006_0003"' in p.read_text(encoding="utf-8")]
    assert children == [MIGRATION.name]


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261006000300_drop_legacy_clause_code_unique.sql"


def test_orm_ddl_is_identical_to_the_migration() -> None:
    module = _load()
    assert intelligence_ddl.FUNCTION_STATEMENTS == module.FUNCTION_STATEMENTS
    assert intelligence_ddl.TRIGGER_STATEMENTS == module.TRIGGER_STATEMENTS
    assert f"WHERE {intelligence_ddl.REUSABLE_KEY_INDEX_WHERE}" in _sql(module.INDEX_STATEMENTS)


def test_no_percent_sign_reaches_op_execute() -> None:
    module = _load()
    assert "%" not in "".join(module.UPGRADE_STATEMENTS + module.DOWNGRADE_STATEMENTS)


def test_every_table_is_force_rls_with_fail_closed_policies_and_no_data_api_access() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    for table in TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in upgrade
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in upgrade
        for operation in ("select", "insert", "update", "delete"):
            assert f"CREATE POLICY {table}_tenant_{operation} ON public.{table}" in upgrade
        assert f"public.{table}" in _load().REVOKE_DATA_API_SQL
    assert upgrade.count("tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid") >= 12
    assert "COALESCE(NULLIF(current_setting" not in upgrade
    for signature in _load().FUNCTION_SIGNATURES:
        assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in upgrade


def test_functions_are_invoker_with_a_pinned_search_path() -> None:
    for statement in _load().FUNCTION_STATEMENTS:
        assert "SECURITY INVOKER" in statement and "SET search_path = public, pg_temp" in statement
        assert "SECURITY DEFINER" not in statement


def test_every_reference_is_a_composite_tenant_project_foreign_key() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    for fragment in (
        "FOREIGN KEY (tenant_id, project_id) REFERENCES public.projects (tenant_id, id) ON DELETE CASCADE",
        "FOREIGN KEY (tenant_id, project_id, target_change_set_id) REFERENCES public.wbs_change_sets (tenant_id, project_id, id)",
        "FOREIGN KEY (tenant_id, project_id, target_baseline_id) REFERENCES public.wbs_baselines (tenant_id, project_id, id)",
        "FOREIGN KEY (tenant_id, project_id, run_id) REFERENCES public.wbs_intelligence_runs (tenant_id, project_id, id)",
        "FOREIGN KEY (tenant_id, project_id, run_id, item_id, item_kind) REFERENCES public.wbs_intelligence_items "
        "(tenant_id, project_id, run_id, id, kind)",
        "FOREIGN KEY (tenant_id, project_id, change_set_id) REFERENCES public.wbs_change_sets (tenant_id, project_id, id)",
    ):
        assert fragment in upgrade, fragment
    for table in TABLES:
        create = next(s for s in _load().UPGRADE_STATEMENTS if f"CREATE TABLE public.{table} " in s)
        assert "tenant_id uuid NOT NULL" in create and "project_id uuid NOT NULL" in create


def test_idempotency_index_never_covers_failed_or_cancelled_runs() -> None:
    index = next(s for s in _load().INDEX_STATEMENTS if "uq_wbs_intelligence_runs_reusable_key" in s)
    assert "CREATE UNIQUE INDEX" in index and "(tenant_id, idempotency_key)" in index
    assert "WHERE status IN ('REQUESTED', 'RUNNING', 'COMPLETED')" in index
    assert "FAILED" not in index and "CANCELLED" not in index
    assert "UNIQUE (tenant_id, idempotency_key)" not in _sql(_load().UPGRADE_STATEMENTS)  # never unconditional


def test_status_and_outcome_are_separate_and_model_provenance_is_never_fabricated() -> None:
    runs = _sql((_load().RUNS_SQL,))
    assert "status IN ('REQUESTED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')" in runs
    assert "outcome IN ('COMPLETE', 'PARTIAL_PROPOSAL', 'INSUFFICIENT_EVIDENCE')" in runs
    assert "(execution_type = 'AI') = (model_provenance IS NOT NULL)" in runs
    assert "qualification IS NOT NULL" in runs  # one coherent report per completed run


def test_items_are_insert_only_and_typed_and_decisions_are_append_only_human_choices() -> None:
    module = _load()
    items_guard = _sql((module.ITEMS_GUARD_FUNCTION_SQL,))
    assert "IF TG_OP = 'UPDATE' THEN RAISE EXCEPTION" in items_guard
    assert "WBS intelligence items are recorded only while their run is RUNNING" in items_guard
    typed = _sql((module.ITEMS_SQL,))
    assert "body ->> 'item_id' = id::text" in typed and "body ->> 'finding_id' = id::text" in typed
    decisions = _sql((module.DECISIONS_SQL,))
    assert "UNIQUE (item_id)" in decisions  # one terminal decision per item
    assert "(item_kind = 'PROPOSAL' AND decision IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT', 'REJECT'))" in decisions
    assert "(item_kind = 'FINDING' AND decision IN ('ACKNOWLEDGE', 'DISMISS', 'NO_CHANGE'))" in decisions
    assert "decided_by_kind = 'human'" in decisions
    assert "APPROVE" not in decisions.replace("APPLY", "")  # no approval vocabulary at all
    guard = _sql((module.DECISIONS_GUARD_FUNCTION_SQL,))
    assert "WBS intelligence decisions are append-only" in guard
    assert "ARRAY['admin', 'user']" in guard and "'deciding a WBS intelligence item'" in guard
    assert "v_cs_status IS DISTINCT FROM 'DRAFT'" in guard
    runs_guard = _sql((module.RUNS_GUARD_FUNCTION_SQL,))
    assert "OLD.status IN ('COMPLETED', 'FAILED', 'CANCELLED')" in runs_guard
    assert "a WBS intelligence run keeps its input identity" in runs_guard


def test_no_seeding_no_wbs_mutation_and_a_scoped_downgrade() -> None:
    module = _load()
    upgrade = _sql(module.UPGRADE_STATEMENTS).upper()
    assert "INSERT INTO" not in upgrade and "DELETE FROM" not in upgrade
    for table in ("WBS_NODES", "WBS_CHANGE_SETS ", "WBS_BASELINES "):
        assert f"ALTER TABLE PUBLIC.{table.strip()} " not in upgrade
        assert f"UPDATE PUBLIC.{table.strip()}" not in upgrade
    downgrade = _sql(module.DOWNGRADE_STATEMENTS)
    assert downgrade.count("DROP TABLE IF EXISTS public.wbs_intelligence_") == 3
    assert "wbs_change_sets" not in downgrade and "wbs_nodes" not in downgrade

"""TS-UT-PC2A2-MIGRATION-001 -- PC-2a.2 governed-apply migration (static guarantees).

Behaviour (upgrade/downgrade, RLS isolation, live-write guard, schema parity with the ORM) runs
on a real PostgreSQL in tests/integration/product_control/test_pc2a2_wbs_governed_apply_migration_db.py
and tests/modules/integration/test_pc2a2_wbs_governed_apply.py.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from src.wbs.adapters.persistence import governed_apply_ddl

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261006_0002_pc2a2_wbs_governed_apply.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(statements: tuple[str, ...]) -> str:
    return re.sub(r"\s+", " ", " ".join(statements))


def test_extends_the_single_chain_after_pc2a1() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261006_0002", "20261006_0001")
    heads = [p.name for p in MIGRATION.parent.glob("*.py") if "down_revision = \"20261006_0002\"" in p.read_text()]
    assert heads == []  # nothing branches off it


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261006000100_pc2a1_wbs_governance_foundation.sql"


def test_orm_ddl_is_identical_to_the_migration() -> None:
    module = _load()
    assert governed_apply_ddl.FUNCTION_STATEMENTS == module.FUNCTION_STATEMENTS
    assert governed_apply_ddl.TRIGGER_STATEMENTS == module.TRIGGER_STATEMENTS


def test_no_percent_sign_reaches_op_execute() -> None:
    module = _load()
    assert "%" not in "".join(module.UPGRADE_STATEMENTS + module.DOWNGRADE_STATEMENTS)


def test_retirements_are_force_rls_with_fail_closed_policies_and_no_data_api_access() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    table = "wbs_change_set_retirements"
    assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in upgrade
    assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in upgrade
    for operation in ("select", "insert", "update", "delete"):
        assert f"CREATE POLICY {table}_tenant_{operation} ON public.{table}" in upgrade
    assert upgrade.count("tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid") >= 4
    assert "COALESCE(NULLIF(current_setting" not in upgrade
    assert "REVOKE ALL ON TABLE public.wbs_change_set_retirements FROM" in upgrade
    for signature in _load().FUNCTION_SIGNATURES:
        assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in upgrade


def test_functions_are_invoker_with_a_pinned_search_path() -> None:
    for statement in _load().FUNCTION_STATEMENTS:
        assert "SECURITY INVOKER" in statement and "SET search_path = public, pg_temp" in statement
        assert "SECURITY DEFINER" not in statement


def test_the_live_write_guard_closes_every_authority_state_and_needs_the_db_apply_state() -> None:
    guard = re.sub(r"\s+", " ", _load().LIVE_WRITE_GUARD_FUNCTION_SQL)
    # no "no baseline yet -> direct writes allowed" exemption (NO_WBS / LEGACY_UNGOVERNED are closed too)
    assert "v_current" not in guard and "CONTINUE WHEN" not in guard
    assert "current_setting('c2pro.wbs_governed_apply', true)" in guard  # a correlation only...
    # ...the gate needs this transaction's baseline row of a SUBMITTED change set of the row's scope
    assert "JOIN public.wbs_baselines b ON b.source_change_set_id = cs.id" in guard
    assert "cs.project_id = v_projects[i] AND cs.tenant_id = v_tenants[i] AND cs.status = 'SUBMITTED'" in guard
    assert "b.parent_baseline_id IS NOT DISTINCT FROM cs.base_baseline_id" in guard  # first baseline: NULL-safe
    assert "b.xmin = pg_current_xact_id()::xid" in guard
    assert "MESSAGE = 'WBS_GOVERNANCE_REQUIRED: " in guard
    # cascades only: inside an FK action, after the project or tenant row is gone
    assert "TG_OP = 'DELETE' AND pg_trigger_depth() > 1" in guard
    trigger = _load().TRIGGER_STATEMENTS[1]
    assert "BEFORE INSERT OR DELETE OR UPDATE OF id, tenant_id, project_id, parent_id, sort_order, code, name" in trigger
    assert "lft" not in trigger and "planned_start" not in trigger  # caches and schedule/cost data stay writable


def test_retirement_dispositions_are_closed_and_legacy_retirement_is_first_baseline_only() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "disposition IN ('REMOVED', 'SPLIT', 'MERGED', 'SUPERSEDED', 'RETIRED_ON_BASELINE')" in upgrade
    assert "disposition <> 'RETIRED_ON_BASELINE' OR source = 'legacy'" in upgrade
    assert "only a first baseline retires live legacy rows of the same project" in upgrade
    assert "WBS retirements are editable only while the change set is DRAFT" in upgrade


def test_no_seeding_no_live_mutation_and_a_scoped_downgrade() -> None:
    module = _load()
    upgrade = _sql(module.UPGRADE_STATEMENTS)
    assert "INSERT INTO" not in upgrade.upper().replace("INSERT INTO PUBLIC.WBS_CHANGE_SET_RETIREMENTS", "")
    assert "UPDATE public.wbs_nodes" not in upgrade and "DELETE FROM" not in upgrade.upper()
    downgrade = _sql(module.DOWNGRADE_STATEMENTS)
    assert "DROP TRIGGER IF EXISTS trg_wbs_nodes_governed_write_guard ON public.wbs_nodes" in downgrade
    assert "DROP TABLE IF EXISTS public.wbs_change_set_retirements" in downgrade
    assert "DROP TABLE IF EXISTS public.wbs_nodes" not in downgrade and "DELETE FROM" not in downgrade.upper()

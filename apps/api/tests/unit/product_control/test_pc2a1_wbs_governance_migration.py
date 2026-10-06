"""TS-UT-PC2A1-MIGRATION-001 -- PC-2a.1 WBS governance migration (static guarantees).

Behaviour (upgrade/downgrade, RLS isolation, immutability, schema parity with the ORM) runs
on a real PostgreSQL in tests/integration/product_control/test_pc2a1_wbs_governance_migration_db.py
and tests/modules/integration/test_pc2a1_wbs_governance_foundation.py. These checks pin what a
reviewer must not lose when editing the SQL.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from src.wbs.adapters.persistence import governance_ddl

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261006_0001_pc2a1_wbs_governance_foundation.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(statements: tuple[str, ...]) -> str:
    return re.sub(r"\s+", " ", " ".join(statements))


def test_extends_the_single_chain() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261006_0001", "20261005_0003")


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261005000300_pc1r_wbs_structural_integrity.sql"


def test_orm_trigger_ddl_is_identical_to_the_migration() -> None:
    """create_all-built schemas must enforce exactly the migrated invariants."""
    module = _load()
    assert governance_ddl.FUNCTION_STATEMENTS == module.FUNCTION_STATEMENTS
    assert governance_ddl.TRIGGER_STATEMENTS == module.TRIGGER_STATEMENTS
    upgrade = _sql(module.UPGRADE_STATEMENTS)
    for check in (governance_ddl.CONTROL_LEVEL_CHECK, governance_ddl.DECOMPOSITION_KIND_CHECK,
                  governance_ddl.DICTIONARY_CHECK):
        assert re.sub(r"\s+", " ", check) in upgrade


def test_no_percent_sign_reaches_op_execute() -> None:
    assert "%" not in "".join(_load().UPGRADE_STATEMENTS + _load().DOWNGRADE_STATEMENTS)


def test_every_governance_table_is_force_rls_with_fail_closed_policies() -> None:
    module = _load()
    upgrade = _sql(module.UPGRADE_STATEMENTS)
    predicate = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"
    for table in module.GOVERNANCE_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in upgrade
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in upgrade
        for operation in ("select", "insert", "update", "delete"):
            assert f"CREATE POLICY {table}_tenant_{operation} ON public.{table}" in upgrade
    assert "COALESCE(NULLIF(current_setting" not in upgrade  # never the fail-open form
    assert upgrade.count(predicate) >= 4 * len(module.GOVERNANCE_TABLES)
    assert "REVOKE ALL ON TABLE public.wbs_change_sets" in upgrade
    assert "REVOKE ALL ON FUNCTION public.wbs_governance_require_user_role(uuid, uuid, text[], text)" in upgrade


def test_authority_is_derived_never_stored() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    for forbidden in ("authority_state", "approved_baseline_id", "applied_baseline_id", "is_approved"):
        assert forbidden not in upgrade


def test_baseline_link_is_one_way_and_one_application() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "CONSTRAINT uq_wbs_baselines_source_change_set UNIQUE (source_change_set_id)" in upgrade
    assert "source_change_set_id uuid NOT NULL" in upgrade
    assert (
        "CREATE UNIQUE INDEX uq_wbs_change_sets_one_application ON public.wbs_change_sets "
        "(project_id, base_baseline_id) NULLS NOT DISTINCT WHERE status = 'APPLIED'" in upgrade
    )
    assert "CONSTRAINT uq_wbs_baselines_linear_history UNIQUE NULLS NOT DISTINCT (project_id, parent_baseline_id)" in upgrade


def test_control_level_is_vocabulary_only() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "control_level IN ('none', 'control_account', 'work_package', 'planning_package')" in upgrade
    # No methodology nesting rule is hard-coded (PC-2b profiles own those).
    assert "control_account" not in upgrade.split("ck_wbs_baseline_nodes_control_level")[1].split("ck_wbs_baseline_nodes_decomposition_kind")[0].replace(
        "control_level IN ('none', 'control_account', 'work_package', 'planning_package')", "")


def test_approval_authority_is_a_human_admin_with_separation_of_duties() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "approved_by_kind = 'human'" in upgrade
    assert "ARRAY['admin'], 'approval'" in upgrade and "ARRAY['admin'], 'approve or reject'" in upgrade
    assert "ARRAY['admin', 'user'], 'submit'" in upgrade
    assert "{wbs_governance,require_distinct_approver}" in upgrade and "'true') <> 'false'" in upgrade


def test_no_live_wbs_mutation_or_legacy_seeding() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "INSERT INTO public.wbs_change_sets" not in upgrade
    assert "INSERT INTO public.wbs_baselines" not in upgrade
    assert "UPDATE public.wbs_nodes" not in upgrade and "DELETE FROM public.wbs_nodes" not in upgrade


def test_trigger_functions_are_invoker_with_pinned_search_path_and_no_public_execute() -> None:
    module = _load()
    for statement in module.FUNCTION_STATEMENTS:
        assert "SECURITY INVOKER" in statement and "SET search_path = public, pg_temp" in statement
        assert "SECURITY DEFINER" not in statement
    upgrade = _sql(module.UPGRADE_STATEMENTS)
    for signature in module.FUNCTION_SIGNATURES:
        assert f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" in upgrade


def test_downgrade_drops_only_what_it_created() -> None:
    downgrade = _sql(_load().DOWNGRADE_STATEMENTS)
    for table in _load().GOVERNANCE_TABLES:
        assert f"DROP TABLE IF EXISTS public.{table}" in downgrade
    assert "DROP TABLE IF EXISTS public.wbs_nodes" not in downgrade
    assert "DELETE FROM" not in downgrade.upper()
    assert "DROP CONSTRAINT IF EXISTS uq_projects_tenant_id" in downgrade

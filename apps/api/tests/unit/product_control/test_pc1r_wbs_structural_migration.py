"""TS-UT-PC1R-MIGRATION-001 -- PC-1R WBS structural-integrity migration (static guarantees).

The data behaviour (preflight without mutation, sort_order backfill, delete safety,
downgrade, RLS unchanged) runs on a real PostgreSQL in
tests/integration/product_control/test_pc1r_wbs_structural_migration_db.py. These
checks pin what a reviewer must not lose when editing the SQL (ADR-029).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261005_0003_pc1r_wbs_structural_integrity.py"
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
    assert (module.revision, module.down_revision) == ("20261005_0003", "20261005_0002")


def test_m6_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261005000200_project_snapshot_partition_rls.sql"


def test_project_is_the_implicit_root_no_single_root_index() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "WHERE parent_id IS NULL" not in upgrade
    assert not re.search(r"UNIQUE INDEX[^;]*\(project_id\)", upgrade)


def test_sibling_order_is_authoritative_and_null_safe() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "ADD COLUMN sort_order integer" in upgrade
    assert (
        "ADD CONSTRAINT uq_wbs_nodes_sibling_order UNIQUE NULLS NOT DISTINCT (project_id, parent_id, sort_order) "
        "DEFERRABLE INITIALLY DEFERRED" in upgrade
    )
    # Backfill preserves the order users see today (nested-set order, then code, then id).
    assert "PARTITION BY project_id, parent_id ORDER BY lft, code, id" in upgrade


def test_parenting_is_same_tenant_and_same_project_without_silent_reroot() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "DROP CONSTRAINT IF EXISTS wbs_nodes_parent_id_fkey" in upgrade
    assert "ADD CONSTRAINT uq_wbs_nodes_tenant_project_id UNIQUE (tenant_id, project_id, id)" in upgrade
    assert (
        "ADD CONSTRAINT fk_wbs_nodes_parent_same_project FOREIGN KEY (tenant_id, project_id, parent_id) "
        "REFERENCES public.wbs_nodes (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED"
        in upgrade
    )
    assert "SET NULL" not in upgrade.split("wbs_nodes_source_document_id_fkey")[0]


def test_code_uniqueness_is_deferrable_for_swaps() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert (
        "ADD CONSTRAINT uq_wbs_nodes_project_code UNIQUE (project_id, code) DEFERRABLE INITIALLY DEFERRED"
        in upgrade
    )


def test_cascade_safety() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert (
        "FOREIGN KEY (source_document_id) REFERENCES public.documents (id) ON DELETE SET NULL" in upgrade
    )
    assert (
        "FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE NO ACTION DEFERRABLE INITIALLY "
        "DEFERRED NOT VALID" in upgrade
    )
    assert "stakeholder_wbs_raci_wbs_item_id_fkey" in upgrade
    assert "procurement_bom_items_wbs_item_id_fkey" in upgrade
    assert "ON DELETE CASCADE" not in upgrade


def test_depth_cache_is_guarded_by_a_deferred_trigger_not_a_check() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    assert "CREATE CONSTRAINT TRIGGER trg_wbs_nodes_hierarchy_cache" in upgrade
    assert "DEFERRABLE INITIALLY DEFERRED" in upgrade
    assert "(parent_id IS NULL) = (depth = 0)" not in upgrade
    assert "CHECK ((parent_id IS NULL)" not in upgrade


def test_preflight_fails_closed_and_sees_every_row() -> None:
    upgrade = _sql(_load().UPGRADE_STATEMENTS)
    # FORCE RLS would hide rows from an owner without BYPASSRLS and make the preflight vacuous.
    assert "NO FORCE ROW LEVEL SECURITY" in upgrade
    assert "FORCE ROW LEVEL SECURITY" in upgrade.replace("NO FORCE ROW LEVEL SECURITY", "")
    for marker in ("missing parent", "cross-project or cross-tenant parent", "parent cycle", "duplicate code"):
        assert marker in upgrade
    assert "RAISE EXCEPTION" in upgrade


def test_downgrade_restores_previous_delete_rules_without_rewriting_data() -> None:
    downgrade = _sql(_load().DOWNGRADE_STATEMENTS)
    assert "REFERENCES public.wbs_nodes (id) ON DELETE SET NULL" in downgrade
    assert "REFERENCES public.documents (id) ON DELETE CASCADE" in downgrade
    assert "DROP COLUMN IF EXISTS sort_order" in downgrade
    assert "DELETE FROM" not in downgrade.upper()
    assert "UPDATE public.wbs_nodes" not in downgrade

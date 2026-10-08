"""PQ-HITL-04B1: schema must fail closed before any finding writer exists."""

from importlib import util
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic/versions/20261008_0001_hitl_finding_decisions.py"
)
MIRROR = (
    Path(__file__).resolve().parents[5]
    / "supabase/migrations/20261008000100_hitl_finding_decisions.sql"
)


def _migration():
    spec = util.spec_from_file_location("hitl_finding_decisions_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finding_ledger_exact_migration_parity() -> None:
    migration = _migration()
    assert migration.revision == "20261008_0001"
    assert migration.down_revision == "20261007_0003"
    assert MIRROR.read_text() == migration.supabase_sql()


def test_ledger_is_append_only_rls_forced_and_no_data_api_writes() -> None:
    ddl = _migration().supabase_sql()
    assert "ENABLE ROW LEVEL SECURITY" in ddl
    assert "FORCE ROW LEVEL SECURITY" in ddl
    assert "NULLIF(current_setting('app.current_tenant', true), '')::uuid" in ddl
    assert "COALESCE(NULLIF(current_setting('app.current_tenant'" not in ddl
    assert "FOR SELECT USING" in ddl
    assert "FOR INSERT WITH CHECK" in ddl
    assert "FOR UPDATE USING" not in ddl
    assert "FOR DELETE USING" not in ddl
    assert "BEFORE UPDATE OR DELETE" in ddl
    assert "RAISE EXCEPTION" in ddl
    assert "REVOKE ALL ON TABLE public.hitl_finding_decisions" in ddl
    assert "anon" in ddl and "authenticated" in ddl
    assert "GRANT ALL ON" not in ddl


def test_database_binds_review_row_and_exact_revision_and_artifact() -> None:
    ddl = _migration().supabase_sql()
    assert "FOREIGN KEY (review_row_id, tenant_id)" in ddl
    assert "FOREIGN KEY (artifact_id, tenant_id, project_id)" in ddl
    assert "FOREIGN KEY (document_revision_id, document_id, project_id, tenant_id)" in ddl
    assert "review_metadata" in ddl and "candidate_binding" in ddl
    assert "lineage_generation" in ddl
    assert "lineage_fencing_token" in ddl
    assert "document_processing_operations" in ddl
    assert "trust_state = 'proposed'" in ddl
    assert "artifact_hash" in ddl
    assert "FOR UPDATE" in ddl  # serial review-row lock in insert guard


def test_revision_cas_idempotency_and_provisional_actions_are_constrained() -> None:
    ddl = _migration().supabase_sql()
    assert "UNIQUE (tenant_id, review_row_id, ledger_revision)" in ddl
    assert "UNIQUE (tenant_id, review_row_id, idempotency_key)" in ddl
    assert "ledger_revision = expected_ledger_revision + 1" in ddl
    assert "finding_id ~ '^[0-9a-f]{64}$'" in ddl
    assert "action IN ('CONFIRMED', 'CORRECTION_PROPOSED', 'DISMISSED', 'NEEDS_INFO')" in ddl
    assert "TRUSTED" not in ddl.split("ck_hitl_finding_action")[1].split(",")[0]
    assert "created_by" in ddl

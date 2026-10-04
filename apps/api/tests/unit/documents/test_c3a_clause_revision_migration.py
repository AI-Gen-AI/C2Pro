"""TS-UT-C3A-MIGRATION-001 - physical revision binding of clauses (static guarantees).

The data behaviour (FK rejection, proven-only backfill and its counts) runs on a
real PostgreSQL in tests/integration/product_control/
test_c3a_clause_revision_migration.py; these checks pin what a reviewer must
not lose when editing the SQL.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261004_0001_clause_revision_binding.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(*fragments: str) -> str:
    return re.sub(r"\s+", " ", " ".join(fragments))


def test_extends_the_single_chain_after_714() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261004_0001", "20260927_0714")


def test_every_statement_is_a_single_statement() -> None:
    module = _load()
    for statement in (*module.UPGRADE_STATEMENTS, *module.DOWNGRADE_STATEMENTS):
        body = re.sub(r"\$(\w*)\$.*?\$\1\$", "", statement, flags=re.DOTALL)
        assert ";" not in body.strip().rstrip(";"), statement[:120]


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    # The mirror sorts after the last applied Supabase migration.
    assert module.SUPABASE_MIRROR > "20261001071400_document_artifact_trust_state.sql"


def test_revision_id_is_nullable_and_bound_by_revision_document_and_tenant() -> None:
    upgrade = _sql(*_load().UPGRADE_STATEMENTS)
    assert "ALTER TABLE public.clauses ADD COLUMN revision_id uuid" in upgrade
    assert "revision_id uuid NOT NULL" not in upgrade
    assert (
        "UNIQUE (revision_id, document_id, tenant_id)" in upgrade
    ), "the FK needs a referenced integrity key on document_revisions"
    assert (
        "FOREIGN KEY (revision_id, document_id, tenant_id) REFERENCES "
        "public.document_revisions (revision_id, document_id, tenant_id)" in upgrade
    )
    assert "ON public.clauses (tenant_id, document_id, revision_id)" in upgrade


def test_no_uniqueness_is_imposed_on_clause_codes() -> None:
    upgrade = _sql(*_load().UPGRADE_STATEMENTS).lower()
    assert "clause_code" not in upgrade


def test_backfill_only_binds_proven_revisions_and_restores_forced_rls() -> None:
    module = _load()
    backfill = _sql(module.BACKFILL_SQL)
    # Valid UUID, an existing revision, the same document and the same tenant.
    assert "evidence_location" in backfill
    assert "~*" in backfill
    assert "r.document_id = c.document_id" in backfill
    assert "r.tenant_id = c.tenant_id" in backfill
    assert "c.revision_id IS NULL" in backfill
    # Row security is lifted for the data step only and restored in the same block.
    assert "NO FORCE ROW LEVEL SECURITY" in backfill
    assert backfill.count("FORCE ROW LEVEL SECURITY") >= 2
    assert module.BACKFILL_SQL in module.UPGRADE_STATEMENTS


def test_backfill_report_classifies_every_row() -> None:
    report = _sql(_load().BACKFILL_REPORT_SQL)
    for column in ("total", "bound", "unbound", "malformed_source", "cross_document_or_tenant"):
        assert f"AS {column}" in report


def test_downgrade_removes_exactly_what_upgrade_added() -> None:
    downgrade = _sql(*_load().DOWNGRADE_STATEMENTS)
    assert "DROP INDEX" in downgrade
    assert "DROP CONSTRAINT fk_clauses_revision_identity" in downgrade
    assert "DROP COLUMN revision_id" in downgrade
    assert "DROP CONSTRAINT uq_document_revisions_identity" in downgrade


def test_orm_declares_the_same_durable_invariant() -> None:
    from src.documents.adapters.persistence.models import ClauseORM
    from src.temporal.adapters.persistence.models import DocumentRevisionORM

    clause_fks = {
        (tuple(fk.column_keys), tuple(e.target_fullname for e in fk.elements))
        for fk in ClauseORM.__table__.foreign_key_constraints
    }
    assert (
        ("revision_id", "document_id", "tenant_id"),
        (
            "document_revisions.revision_id",
            "document_revisions.document_id",
            "document_revisions.tenant_id",
        ),
    ) in clause_fks
    assert ClauseORM.__table__.c.revision_id.nullable is True
    unique_sets = {
        tuple(c.name for c in constraint.columns)
        for constraint in DocumentRevisionORM.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("revision_id", "document_id", "tenant_id") in unique_sets

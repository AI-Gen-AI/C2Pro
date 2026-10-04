"""TS-UT-C3B1-MIGRATION-001 - trusted-artifact materialization schema (static guarantees).

The data behaviour (idempotency index, scope FK, historical rows never scheduled)
runs on a real PostgreSQL in tests/modules/integration/
test_c3b1_trusted_materialization.py; these checks pin what a reviewer must not
lose when editing the SQL.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261004_0002_trusted_artifact_materialization.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(*fragments: str) -> str:
    return re.sub(r"\s+", " ", " ".join(fragments))


def test_extends_the_single_chain_after_c3a() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261004_0002", "20261004_0001")


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261004000100_clause_revision_binding.sql"


def test_existing_obligations_are_never_scheduled_for_materialization() -> None:
    upgrade = _sql(*_load().UPGRADE_STATEMENTS)
    # Every pre-existing row (historical trusted artifacts) gets not_required.
    assert "ADD COLUMN materialization_state varchar(24) NOT NULL DEFAULT 'not_required'" in upgrade
    # The migration never writes 'pending' into existing rows.
    assert "UPDATE" not in upgrade.upper()


def test_projection_obligation_semantics_are_untouched() -> None:
    upgrade = _sql(*_load().UPGRADE_STATEMENTS)
    for projection_column in ("projection_state", "enqueue_attempts", "last_checked_at"):
        assert projection_column not in upgrade
    assert "materialization_attempts" in upgrade
    assert "materialization_checked_at" in upgrade


def test_one_materialization_per_artifact_within_its_own_scope() -> None:
    upgrade = _sql(*_load().UPGRADE_STATEMENTS)
    assert "ALTER TABLE public.analyses ADD COLUMN source_artifact_id uuid NULL" in upgrade
    assert (
        "CREATE UNIQUE INDEX uq_analyses_source_artifact ON public.analyses (source_artifact_id) "
        "WHERE source_artifact_id IS NOT NULL" in upgrade
    )
    assert "UNIQUE (artifact_id, tenant_id, project_id)" in upgrade
    assert (
        "FOREIGN KEY (source_artifact_id, tenant_id, project_id) REFERENCES "
        "public.document_artifacts (artifact_id, tenant_id, project_id)" in upgrade
    )


def test_no_alert_identity_schema_is_added_here() -> None:
    # Alert identity / reconciliation belongs to the canonical Alerts work (#828).
    upgrade = _sql(*_load().UPGRADE_STATEMENTS).lower()
    assert "alerts" not in upgrade
    assert "fingerprint" not in upgrade


def test_downgrade_removes_exactly_what_upgrade_added() -> None:
    downgrade = _sql(*_load().DOWNGRADE_STATEMENTS)
    for name in (
        "uq_analyses_source_artifact",
        "fk_analyses_source_artifact_scope",
        "source_artifact_id",
        "uq_document_artifacts_scope",
        "ix_trusted_projection_index_materialization_pending",
        "ck_trusted_projection_index_materialization_state",
        "materialization_state",
    ):
        assert name in downgrade

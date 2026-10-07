"""#686: least-privileged recovery authority read grant contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261007_0002_p0c_recovery_authority_read_grant.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"

ROLE = "c2pro_prod_acceptance_ro"
TABLE = "public.document_processing_operations"
ALLOWED_COLUMNS = (
    "document_id",
    "tenant_id",
    "revision_id",
    "generation",
    "stage",
    "phase",
    "outcome",
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extends_current_single_chain() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261007_0002", "20261007_0001")


def test_grant_is_column_scoped_and_rls_guarded() -> None:
    module = _load()
    upgrade = "\n".join(module.UPGRADE_STATEMENTS)
    assert "relrowsecurity" in upgrade
    assert "relforcerowsecurity" in upgrade
    assert ROLE in upgrade
    assert TABLE in upgrade
    for column in ALLOWED_COLUMNS:
        assert column in upgrade
    assert "last_error" not in upgrade
    assert "owner_token" not in upgrade
    assert "fencing_token" not in upgrade
    assert "lease_expires_at" not in upgrade
    assert "GRANT SELECT ON" not in upgrade


def test_downgrade_revokes_only_column_scoped_access() -> None:
    module = _load()
    downgrade = "\n".join(module.DOWNGRADE_STATEMENTS)
    assert ROLE in downgrade
    assert TABLE in downgrade
    assert "REVOKE SELECT (" in downgrade
    assert "REVOKE ALL" not in downgrade


def test_supabase_mirror_matches_upgrade() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()

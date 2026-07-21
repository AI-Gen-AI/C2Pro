"""TS-SEC-RLS-CLAUSE-EMBEDDINGS-001.

Regression checks for clause_embeddings RLS hardening migration.
"""

from pathlib import Path


def test_clause_embeddings_rls_hardening_migration_contains_policy() -> None:
    migration = (
        Path(__file__).resolve().parents[6]
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "20260421_0001_harden_clause_embeddings_rls.py"
    )
    assert migration.exists()

    contents = migration.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in contents
    assert "FORCE ROW LEVEL SECURITY" in contents
    assert "CREATE POLICY {_POLICY_NAME}" in contents
    assert '_POLICY_NAME = "clause_embeddings_tenant_isolation"' in contents
    assert "current_setting('app.current_tenant'" in contents
    assert "FROM projects p" in contents

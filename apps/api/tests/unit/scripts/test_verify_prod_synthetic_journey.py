from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "verify_prod_synthetic_journey.py"
SPEC = spec_from_file_location("verify_prod_synthetic_journey", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_normalize_database_url_uses_asyncpg() -> None:
    assert MODULE._normalize_database_url("postgresql://example/db").startswith(
        "postgresql+asyncpg://"
    )
    assert MODULE._normalize_database_url("postgres://example/db").startswith(
        "postgresql+asyncpg://"
    )


def test_normalize_database_url_rejects_non_postgres_scheme() -> None:
    with pytest.raises(MODULE.VerificationFailure, match="PostgreSQL scheme"):
        MODULE._normalize_database_url("https://attacker.invalid/db")


def test_uuid_rejects_malformed_identifier_without_echoing_value() -> None:
    raw = "not-a-real-sensitive-id"
    with pytest.raises(MODULE.VerificationFailure) as exc:
        MODULE._uuid(raw, "tenant id")
    assert raw not in str(exc.value)


def test_synthetic_tenant_preflight_requires_durable_marker_and_clerk_binding() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "settings ->> \'synthetic_acceptance\'" in source
    assert "clerk_org_id = :clerk_org_id" in source
    assert "name NOT LIKE \'ACCEPT-706-%\'" in source


def test_all_business_queries_are_explicitly_tenant_project_scoped() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for table in ("projects", "documents", "clauses", "document_chunks", "analyses", "document_artifacts", "project_events", "project_snapshots", "review_items"):
        marker = f"FROM {table}"
        positions = []
        start = 0
        while True:
            index = source.find(marker, start)
            if index < 0:
                break
            positions.append(index)
            start = index + len(marker)
        assert positions, table
        for index in positions:
            window = source[index:index + 500]
            assert "tenant_id = :tenant_id" in window
            if table != "projects" or "name NOT LIKE" not in window:
                assert "project_id = :project_id" in window or "id = :project_id" in window


def test_verifier_forces_read_only_transaction_and_has_no_write_sql() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'text("SET TRANSACTION READ ONLY")' in source
    for keyword in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert keyword not in source


def test_verifier_sets_tenant_rls_context_inside_readonly_transaction() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    read_only = source.index('text("SET TRANSACTION READ ONLY")')
    rls_context = source.index(
        'text("SELECT set_config(\'app.current_tenant\', :tenant_id, true)")'
    )
    preflight = source.index("checks = await _preflight_checks(")
    assert read_only < rls_context < preflight
    assert "{TENANT_ID_KEY: str(tenant_id)}" in source
    assert "BYPASSRLS" not in source


def test_verifier_output_path_is_fixed_to_canonical_evidence_file(tmp_path: Path) -> None:
    expected = tmp_path / "evidence/product-qualification/runtime/verifier.json"
    assert MODULE._verifier_output_path(repo_root=tmp_path) == expected

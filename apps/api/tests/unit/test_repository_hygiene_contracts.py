"""Repository hygiene contracts for C2PRO-DEV-15 Wave 2."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_legacy_root_document_repository_test_is_removed() -> None:
    """Legacy skipped test must not remain as a misleading RLS authority."""

    assert not (_repo_root() / "apps" / "api" / "test_document_repository.py").exists()


def test_document_repository_integration_note_points_to_live_rls_authorities() -> None:
    """Repository docs/tests must point at active PostgreSQL/RLS coverage."""

    repo_root = _repo_root()
    api_root = repo_root / "apps" / "api"
    integration_path = (
        api_root
        / "tests"
        / "modules"
        / "integration"
        / "test_document_repository_db.py"
    )
    postgres_read_authority = (
        api_root
        / "tests"
        / "integration"
        / "documents"
        / "test_clause_evidence_read_port_db.py"
    )
    rls_authority = api_root / "tests" / "security" / "test_rls_real_enforcement.py"

    assert postgres_read_authority.is_file()
    assert rls_authority.is_file()

    integration = integration_path.read_text(encoding="utf-8")
    postgres_reference = postgres_read_authority.relative_to(api_root).as_posix()
    rls_reference = rls_authority.relative_to(api_root).as_posix()

    assert postgres_reference in integration
    assert rls_reference in integration
    assert "test_document_repository.py" not in integration

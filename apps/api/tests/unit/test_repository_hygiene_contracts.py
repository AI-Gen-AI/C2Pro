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
    integration = (
        repo_root
        / "apps"
        / "api"
        / "tests"
        / "modules"
        / "integration"
        / "test_document_repository_db.py"
    ).read_text(encoding="utf-8")

    assert "tests/adapters/persistence/test_documents_repository.py" in integration
    assert "tests/security/test_rls_real_enforcement.py" in integration
    assert "see test_document_repository.py" not in integration

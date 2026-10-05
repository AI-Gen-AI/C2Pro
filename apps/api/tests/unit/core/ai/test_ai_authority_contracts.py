"""Core AI authority contracts for C2PRO-DEV-15 Wave 3."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def test_fallback_authority_is_not_duplicated_under_core_ai() -> None:
    """Fallback ownership stays with the analysis adapter implementation."""

    repo_root = _repo_root()
    legacy = repo_root / "apps" / "api" / "src" / "core" / "ai" / "fallback_client.py"
    canonical = (
        repo_root
        / "apps"
        / "api"
        / "src"
        / "analysis"
        / "adapters"
        / "ai"
        / "llm_fallback_client.py"
    )

    assert not legacy.exists()
    assert canonical.exists()
    canonical_source = canonical.read_text(encoding="utf-8")
    assert "class FallbackAIClient" in canonical_source
    assert "class CircuitBreaker" in canonical_source


def test_deleted_fallback_duplicate_is_not_hidden_from_coverage_config() -> None:
    """Coverage config must not retain stale omissions for removed AI modules."""

    repo_root = _repo_root()
    pyproject = (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")

    assert "src/core/ai/fallback_client.py" not in pyproject

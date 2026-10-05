"""Coverage-governance contracts for C2PRO-DEV-15 Core AI assurance."""

from __future__ import annotations

import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def test_proven_core_ai_modules_are_not_excluded_from_coverage() -> None:
    """Production Core AI modules with meaningful tests must count toward coverage."""

    repo_root = _repo_root()
    pyproject = tomllib.loads(
        (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert "src/core/ai/cost_controller.py" not in omitted
    assert "src/core/ai/token_counter.py" not in omitted
    assert "src/core/ai/validators/*" not in omitted

"""Canonical Core AI test-layout contracts for C2PRO-DEV-15."""

from __future__ import annotations

import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def test_langsmith_prompt_pytest_modules_live_under_tests_tree() -> None:
    repo_root = _repo_root()
    source_ai = repo_root / "apps" / "api" / "src" / "core" / "ai"
    tests_ai = repo_root / "apps" / "api" / "tests" / "unit" / "core" / "ai"

    for name in (
        "test_prompt_registry.py",
        "test_langsmith_client.py",
        "test_sync_prompts_cli.py",
    ):
        assert not (source_ai / name).exists()
        assert (tests_ai / name).exists()


def test_prompt_sync_modules_are_measured_by_coverage() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads(
        (repo_root / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    omitted = set(pyproject["tool"]["coverage"]["run"]["omit"])

    assert "src/core/ai/prompt_registry.py" not in omitted
    assert "src/core/ai/sync_prompts.py" not in omitted

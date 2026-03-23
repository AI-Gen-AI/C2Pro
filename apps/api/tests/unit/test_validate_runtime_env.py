"""TS-OPS-ENV-GUARD-001

Regression checks for runtime/test environment guardrails.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "scripts" / "validate_runtime_env.py"
    spec = importlib.util.spec_from_file_location("validate_runtime_env", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_guard_rejects_test_database_for_manual_qa() -> None:
    module = _load_module()

    with pytest.raises(module.RuntimeEnvValidationError, match="test database"):
        module.validate_runtime_env(
            database_url="postgresql://postgres:postgres@localhost:5433/c2pro_test",
            environment="development",
        )


def test_runtime_guard_allows_non_test_database_for_manual_qa() -> None:
    module = _load_module()

    result = module.validate_runtime_env(
        database_url="postgresql://app:secret@db.example.com/c2pro_dev",
        environment="development",
    )

    assert result.database_name == "c2pro_dev"
    assert result.environment == "development"


def test_runtime_guard_allows_test_environment_to_use_test_database() -> None:
    module = _load_module()

    result = module.validate_runtime_env(
        database_url="postgresql://postgres:postgres@localhost:5433/c2pro_test",
        environment="test",
    )

    assert result.database_name == "c2pro_test"

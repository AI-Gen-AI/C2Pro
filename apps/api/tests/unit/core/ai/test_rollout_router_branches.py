"""TS-AI-LANGSMITH-032: LangSmithRolloutConfig.from_env branch coverage."""

from __future__ import annotations

import pytest

from src.core.ai.rollout_router import LangSmithRolloutConfig


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("LANGSMITH_ROLLOUT_PERCENTAGE", "LANGSMITH_ROLLOUT_FAIL_OPEN"):
        monkeypatch.delenv(key, raising=False)


def test_from_env_valid_percentage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_ROLLOUT_PERCENTAGE", "50")
    monkeypatch.setenv("LANGSMITH_ROLLOUT_FAIL_OPEN", "0")

    config = LangSmithRolloutConfig.from_env()

    assert config.rollout_percentage == 50
    assert config.fail_open_enabled is False


def test_from_env_percentage_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_ROLLOUT_PERCENTAGE", "150")

    with pytest.raises(
        ValueError, match="LANGSMITH_ROLLOUT_PERCENTAGE must be between 0 and 100"
    ):
        LangSmithRolloutConfig.from_env()


def test_from_env_fail_open_true_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv("LANGSMITH_ROLLOUT_FAIL_OPEN", value)
        config = LangSmithRolloutConfig.from_env()
        assert config.fail_open_enabled is True, f"{value!r} should be truthy"


def test_from_env_fail_open_false_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("0", "false", "no", "off"):
        monkeypatch.setenv("LANGSMITH_ROLLOUT_FAIL_OPEN", value)
        config = LangSmithRolloutConfig.from_env()
        assert config.fail_open_enabled is False, f"{value!r} should be false"

    monkeypatch.setenv("LANGSMITH_ROLLOUT_FAIL_OPEN", "")
    config = LangSmithRolloutConfig.from_env()
    assert config.fail_open_enabled is False, "empty string should be false"

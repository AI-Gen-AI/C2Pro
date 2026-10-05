"""TS-UT-C3B1-SKIP-HITL-001 - a non-resumable PROPOSED candidate cannot arise in production.

Lane C / C3b-1 policy PRODUCTION_FORBIDDEN: ``C2PRO_SKIP_HITL`` (like
``C2PRO_AI_MOCK``) routes a run past the HITL interrupt, leaving a PROPOSED
candidate that no canonical approval can reach. Production refuses to start
with it, and the routing point ignores it there even if the environment is
mis-set (the run pauses for a real human decision instead).
"""

from __future__ import annotations

import pytest

from src.analysis.adapters.graph import workflow
from src.config import Settings


def test_production_settings_refuse_skip_hitl(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only the flag under test: the other mock flags have their own guards.
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.delenv("C2PRO_EMBEDDINGS_MOCK", raising=False)
    monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
    with pytest.raises(ValueError, match="C2PRO_SKIP_HITL cannot be enabled in production"):
        Settings(environment="production")


def test_non_production_settings_still_allow_the_operator_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
    assert Settings(environment="test").skip_hitl is True


@pytest.mark.parametrize("flag", ["C2PRO_SKIP_HITL", "C2PRO_AI_MOCK"])
def test_routing_never_skips_the_gate_in_production(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.delenv("C2PRO_SKIP_HITL", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert workflow._skip_hitl_requested() is False

    monkeypatch.setenv("ENVIRONMENT", "test")
    assert workflow._skip_hitl_requested() is True


def test_routing_without_any_flag_never_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("C2PRO_SKIP_HITL", raising=False)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    assert workflow._skip_hitl_requested() is False

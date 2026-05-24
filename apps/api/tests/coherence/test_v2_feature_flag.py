"""
Tests for the ECOA v2 feature flag (ADR-009 §7.2 step 4).

Refers to Suite ID: TS-UC-COH-V2-FLAG-001.
"""
from __future__ import annotations

import pytest

from src.config import Settings


@pytest.mark.unit
def test_coherence_v2_enabled_defaults_to_false() -> None:
    s = Settings()
    assert s.coherence_v2_enabled is False


@pytest.mark.unit
def test_coherence_v2_shadow_mode_defaults_to_true() -> None:
    s = Settings()
    assert s.coherence_v2_shadow_mode is True


@pytest.mark.unit
def test_flag_can_be_overridden_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERENCE_V2_ENABLED", "true")
    monkeypatch.setenv("COHERENCE_V2_SHADOW_MODE", "false")
    s = Settings()
    assert s.coherence_v2_enabled is True
    assert s.coherence_v2_shadow_mode is False

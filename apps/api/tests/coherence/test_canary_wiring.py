"""
ADR-017 canary wiring: flag-gated canonical re-score on /evaluate.

The canary flips only the SCORER — off ⇒ the v1 result is returned untouched; on ⇒ the
headline is re-derived through the canonical scorer while findings/alerts are unchanged.

Refers to Suite ID: TS-UA-COH-CANARY-WIRING-001.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from src.coherence.canonical.live_rescore import canonical_rescore
from src.coherence.models import CategoryBreakdown, EnrichedCoherenceResult, SeverityCount
from src.coherence.router import _apply_canonical_rescore, _maybe_apply_canonical_canary

_CLEAN = ("SCHEDULE", "SCOPE", "TECHNICAL", "LEGAL", "QUALITY")


class _StubFlags:
    """Minimal TenantFlagsService stand-in returning a fixed enrolment."""

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    async def is_enabled(self, tenant_id: Any, flag: str) -> bool:
        return self._enabled


def _result_with_critical() -> EnrichedCoherenceResult:
    """A result v1 scored 65 (flat −35 for a critical); canonical caps it at the 85 ceiling."""
    breakdown = [
        CategoryBreakdown(
            category="BUDGET", score=65.0, alert_count=1,
            severity_breakdown=SeverityCount(critical=1), impact_percentage=100.0,
            state="assessed_findings",
        )
    ]
    breakdown += [
        CategoryBreakdown(
            category=c, score=100.0, alert_count=0,  # type: ignore[arg-type]
            severity_breakdown=SeverityCount(), impact_percentage=0.0, state="assessed_clean",
        )
        for c in _CLEAN
    ]
    return EnrichedCoherenceResult(
        overall_score=65.0, category_breakdown=breakdown, score_version="coherence-v1"
    )


@pytest.mark.unit
def test_canary_off_returns_v1_unchanged() -> None:
    result = _result_with_critical()
    out = asyncio.run(
        _maybe_apply_canonical_canary(
            result, tenant_id=uuid.uuid4(), flags_service=_StubFlags(False)
        )
    )
    assert out is result  # byte-identical v1 path
    assert out.overall_score == pytest.approx(65.0)
    assert out.score_version == "coherence-v1"


@pytest.mark.unit
def test_canary_without_flags_service_is_off() -> None:
    result = _result_with_critical()
    out = asyncio.run(
        _maybe_apply_canonical_canary(result, tenant_id=uuid.uuid4(), flags_service=None)
    )
    assert out is result


@pytest.mark.unit
def test_canary_on_returns_canonical_headline() -> None:
    result = _result_with_critical()
    out = asyncio.run(
        _maybe_apply_canonical_canary(
            result, tenant_id=uuid.uuid4(), flags_service=_StubFlags(True)
        )
    )
    assert out.overall_score == pytest.approx(85.0)  # §G.1 recalibrated critical ceiling
    assert out.score_version == "coherence-v2"
    assert out.score_reason  # a canary reason is stamped
    # Detection is unchanged: BUDGET is still the flagged category, just re-scored.
    budget = next(cb for cb in out.category_breakdown if cb.category == "BUDGET")
    assert budget.score is not None and budget.score < 50.0


@pytest.mark.unit
def test_apply_canonical_rescore_is_immutable() -> None:
    result = _result_with_critical()
    rescore = canonical_rescore(result.category_breakdown)
    out = _apply_canonical_rescore(result, rescore)
    assert out.overall_score == rescore.score
    assert out.score_version == "coherence-v2"
    assert result.overall_score == pytest.approx(65.0)  # original untouched (model_copy)

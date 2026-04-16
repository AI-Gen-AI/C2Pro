"""Unit tests for CoherenceScoringPortAdapter.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.decision_intelligence.adapters.ports.coherence_scoring_port_adapter import (
    CoherenceScoringPortAdapter,
    _normalize_score,
)


def test_normalize_score_zero_returns_one() -> None:
    assert _normalize_score(0) == 1.0


def test_normalize_score_decays_with_alerts() -> None:
    assert _normalize_score(1.0) == pytest.approx(0.606531, rel=1e-4)
    assert _normalize_score(5.0) == pytest.approx(0.082085, rel=1e-3)


def test_normalize_score_floor() -> None:
    assert _normalize_score(100.0) == 0.05


@pytest.mark.asyncio
async def test_aggregate_calls_service_and_wraps_result() -> None:
    overall = SimpleNamespace(score=0.0, severity="Low", explanation={"reason": "clean"})
    service = SimpleNamespace(aggregate_coherence_score=AsyncMock(return_value=overall))
    adapter = CoherenceScoringPortAdapter(service=service)  # type: ignore[arg-type]

    result = await adapter.aggregate_coherence_score([], uuid4(), uuid4())

    assert result["score"] == 1.0
    assert result["severity"] == "Low"
    assert result["explanation"] == {"reason": "clean"}
    assert result["metadata"]["source"] == "coherence_scoring_service"
    assert result["metadata"]["alert_count"] == 0


@pytest.mark.asyncio
async def test_aggregate_falls_back_on_service_error() -> None:
    service = SimpleNamespace(
        aggregate_coherence_score=AsyncMock(side_effect=RuntimeError("bad profile"))
    )
    adapter = CoherenceScoringPortAdapter(service=service)  # type: ignore[arg-type]
    result = await adapter.aggregate_coherence_score([], uuid4(), uuid4())
    assert result["metadata"]["source"] == "fallback"
    assert 0 < result["score"] <= 1


@pytest.mark.asyncio
async def test_aggregate_skips_invalid_alerts() -> None:
    overall = SimpleNamespace(score=0.0, severity="Low", explanation={})
    service = SimpleNamespace(aggregate_coherence_score=AsyncMock(return_value=overall))
    adapter = CoherenceScoringPortAdapter(service=service)  # type: ignore[arg-type]

    await adapter.aggregate_coherence_score(
        [{"not": "a valid alert"}, 42, None],  # type: ignore[list-item]
        uuid4(),
        uuid4(),
    )

    call_alerts = service.aggregate_coherence_score.await_args.kwargs["alerts"]
    assert call_alerts == []

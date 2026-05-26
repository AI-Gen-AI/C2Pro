"""
Tests for the Shadow Mode dual-run runner (ADR-009 §7.2 step 5, §21).

Refers to Suite ID: TS-UA-COH-V2-SHADOW-001.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    CoherenceV2Payload,
    GlobalV2,
)
from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.coherence.services.v2.shadow_runner import ShadowDelta, ShadowRunner


def _v1(score: float | None = 80.0) -> dict:
    return {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "coherence_score": score,
        "global_score": score,
        "sub_scores": {c: 80 for c in
                       ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")},
        "weights_used": {},
        "alert_count": 0,
        "document_count": 5,
        "methodology_version": "v1",
        "score_version": SCORE_VERSION_V1,
    }


def _v2(score: float | None = 78.0,
        active_weight: float = 1.0,
        completeness: float = 1.0,
        tri: float = 0.9) -> CoherenceV2Payload:
    return CoherenceV2Payload(
        project_id=uuid4(),
        generated_at=datetime.now(UTC),
        **{
            "global": GlobalV2(
                coherence_score=score,
                completeness_score=completeness,
                technical_reliability_index=tri,
                status="scored" if score is not None else "insufficient_active_weight",
                score_reason="scored_categories_only" if score else "insufficient_active_weight",
                active_weight=active_weight,
            )
        },
        categories=[
            CategoryV2(
                category=c,
                status=CategoryStatus.SCORED,
                coherence_score=80.0,
                evidence_coverage=1.0,
                technical_reliability=tri,
                evidence_freshness=1.0,
            )
            for c in ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
        ],
    )


@pytest.mark.unit
def test_compare_returns_shadow_delta() -> None:
    runner = ShadowRunner()
    delta: ShadowDelta = runner.compare(_v1(80.0), _v2(78.0))
    assert isinstance(delta, ShadowDelta)
    assert delta.delta_abs == pytest.approx(2.0, rel=1e-6)
    assert delta.delta_signed == pytest.approx(-2.0, rel=1e-6)
    assert delta.coherence_v1_score == 80.0
    assert delta.coherence_v2_score == 78.0


@pytest.mark.unit
def test_compare_handles_nulls_gracefully() -> None:
    runner = ShadowRunner()
    delta = runner.compare(_v1(None), _v2(None))
    assert delta.delta_abs is None
    assert delta.delta_signed is None


@pytest.mark.unit
def test_emit_logs_structured_event(caplog: pytest.LogCaptureFixture) -> None:
    runner = ShadowRunner()
    delta = runner.compare(_v1(80.0), _v2(78.0))
    with caplog.at_level(logging.INFO):
        runner.emit(delta)
    records = [r for r in caplog.records if "coherence.shadow.delta" in r.getMessage()]
    assert records, "expected coherence.shadow.delta log event"


@pytest.mark.unit
def test_emit_payload_excludes_clause_text(caplog: pytest.LogCaptureFixture) -> None:
    runner = ShadowRunner()
    delta = runner.compare(_v1(80.0), _v2(78.0))
    with caplog.at_level(logging.INFO):
        runner.emit(delta)
    for r in caplog.records:
        msg = r.getMessage().lower()
        assert "clause" not in msg or "categories" in msg  # category id only
        assert "ocr" not in msg
        assert "quote" not in msg


@pytest.mark.unit
def test_delta_contains_required_fields() -> None:
    runner = ShadowRunner()
    delta = runner.compare(_v1(80.0), _v2(78.0))
    payload = delta.to_log_event(feature_flag_state={"coherence_v2_enabled": True,
                                                     "coherence_v2_shadow_mode": True})
    required_fields = {
        "project_id",
        "tenant_id",
        "coherence_v1_score",
        "coherence_v2_score",
        "delta_abs",
        "delta_signed",
        # Canonical score_version labels (Phase F)
        "score_version_v1",
        "score_version_v2",
        "v1_status",
        "v2_status",
        "v2_active_weight",
        "v2_completeness_score",
        "v2_technical_reliability_index",
        "v2_score_reason",
        "evaluated_categories",
        "missing_categories",
        "conflicting_categories",
        "model_version",
        "feature_flag_state",
        "generated_at",
    }
    assert required_fields.issubset(payload.keys())

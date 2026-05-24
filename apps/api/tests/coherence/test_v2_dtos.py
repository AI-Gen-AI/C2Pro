"""
Tests for ECOA v2 Pydantic DTOs (ADR-009 §5, §7.1).

Refers to Suite ID: TS-UA-COH-V2-DTO-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    CoherenceV2Payload,
    GlobalV2,
    ScoreExplanation,
)


@pytest.mark.unit
def test_status_enum_has_six_states() -> None:
    assert {s.value for s in CategoryStatus} == {
        "pending_documents",
        "insufficient_evidence",
        "scored",
        "conflicting_evidence",
        "not_applicable",
        "processing_error",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        CategoryStatus.INSUFFICIENT_EVIDENCE,
        CategoryStatus.PENDING_DOCUMENTS,
        CategoryStatus.NOT_APPLICABLE,
    ],
)
def test_score_must_be_null_when_no_evidence(status: CategoryStatus) -> None:
    with pytest.raises(ValidationError):
        CategoryV2(
            category="BUDGET",
            status=status,
            coherence_score=42.0,
            evidence_coverage=0.5,
            technical_reliability=0.5,
            evidence_freshness=0.5,
        )


@pytest.mark.unit
def test_scored_status_allows_numeric_score() -> None:
    cat = CategoryV2(
        category="BUDGET",
        status=CategoryStatus.SCORED,
        coherence_score=72.5,
        evidence_coverage=0.8,
        technical_reliability=0.9,
        evidence_freshness=0.7,
        score_explanation=ScoreExplanation(),
    )
    assert cat.coherence_score == 72.5


@pytest.mark.unit
def test_conflicting_evidence_allows_numeric_score() -> None:
    cat = CategoryV2(
        category="BUDGET",
        status=CategoryStatus.CONFLICTING_EVIDENCE,
        coherence_score=12.0,
        evidence_coverage=0.5,
        technical_reliability=0.6,
        evidence_freshness=0.5,
        score_explanation=ScoreExplanation(negative_factors=["hard_conflict"]),
    )
    assert cat.coherence_score == 12.0


@pytest.mark.unit
def test_version_literal_locked() -> None:
    payload = CoherenceV2Payload(
        project_id=uuid4(),
        generated_at=datetime.now(UTC),
        **{
            "global": GlobalV2(
                coherence_score=None,
                completeness_score=0.0,
                technical_reliability_index=0.0,
                status="pending_documents",
                score_reason="no_documents_uploaded",
                active_weight=0.0,
            )
        },
        categories=[],
    )
    assert payload.version == "coherence-v2"


@pytest.mark.unit
def test_payload_serializes_global_field_alias() -> None:
    payload = CoherenceV2Payload(
        project_id=uuid4(),
        generated_at=datetime.now(UTC),
        **{
            "global": GlobalV2(
                coherence_score=80.0,
                completeness_score=1.0,
                technical_reliability_index=0.9,
                status="scored",
                score_reason="scored_categories_only",
                active_weight=1.0,
            )
        },
        categories=[],
    )
    dumped = payload.model_dump(by_alias=True)
    assert "global" in dumped
    assert "global_" not in dumped


@pytest.mark.unit
def test_payload_roundtrip_json() -> None:
    payload = CoherenceV2Payload(
        project_id=uuid4(),
        generated_at=datetime.now(UTC),
        **{
            "global": GlobalV2(
                coherence_score=None,
                completeness_score=0.0,
                technical_reliability_index=0.0,
                status="insufficient_active_weight",
                score_reason="insufficient_active_weight",
                active_weight=0.20,
            )
        },
        categories=[
            CategoryV2(
                category="SCOPE",
                status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                coherence_score=None,
                evidence_coverage=0.1,
                technical_reliability=0.0,
                evidence_freshness=0.0,
            )
        ],
    )
    json_str = payload.model_dump_json(by_alias=True)
    rebuilt = CoherenceV2Payload.model_validate_json(json_str)
    assert rebuilt.version == "coherence-v2"
    assert rebuilt.categories[0].coherence_score is None
    assert rebuilt.global_.coherence_score is None
    assert rebuilt.global_.score_reason == "insufficient_active_weight"


@pytest.mark.unit
def test_score_explanation_has_four_arrays() -> None:
    exp = ScoreExplanation()
    assert exp.positive_factors == []
    assert exp.negative_factors == []
    assert exp.dominant_rules == []
    assert exp.score_path == []

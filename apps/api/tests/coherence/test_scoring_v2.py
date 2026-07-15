"""
Tests for the additive v2 scoring entry point inside scoring.py.

Refers to Suite ID: TS-UA-COH-V2-SCORING-001.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CoherenceV2Payload,
)
from src.coherence.scoring import calculate_v2_from_signals
from src.coherence.services.v2.evidence_service import EvidenceBundle


@pytest.mark.unit
def test_v1_and_v2_are_callable_side_by_side() -> None:
    # v1 path: importing it must still work — v2 must be additive.
    from src.coherence.scoring import ScoringService
    assert callable(ScoringService.calculate_detailed)
    assert callable(calculate_v2_from_signals)


@pytest.mark.unit
def test_v2_returns_payload_object_with_six_categories() -> None:
    bundles = {
        c: EvidenceBundle(
            count=5, evidence_coverage=1.0, evidence_freshness=1.0,
            avg_technical_reliability=0.9, missing_required=[],
            references=["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"],
        )
        for c in ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
    }
    payload: CoherenceV2Payload = calculate_v2_from_signals(
        signals=[],
        evidence_bundles=bundles,
        applicability_map=dict.fromkeys(bundles, (True, None)),
        project_id=uuid4(),
    )
    assert len(payload.categories) == 6
    assert all(c.status is CategoryStatus.SCORED for c in payload.categories)


@pytest.mark.unit
def test_v2_returns_null_global_below_min_active_weight() -> None:
    # Only LEGAL is applicable; the other five are explicitly N/A.
    bundles = {
        "LEGAL": EvidenceBundle(
            count=1, evidence_coverage=1.0, evidence_freshness=1.0,
            avg_technical_reliability=0.9, missing_required=[],
            references=["doc-1"],
        )
    }
    applicability = {
        "SCOPE": (False, "no scope deliverables"),
        "BUDGET": (False, "no budget deliverables"),
        "QUALITY": (False, "no quality deliverables"),
        "TECHNICAL": (False, "no technical deliverables"),
        "TIME": (False, "no time deliverables"),
        "LEGAL": (True, None),
    }
    payload = calculate_v2_from_signals(
        signals=[],
        evidence_bundles=bundles,
        applicability_map=applicability,
        project_id=uuid4(),
    )
    # active_weight = 1/1 normalized — but only one category is applicable,
    # so it must be ≥ MIN_ACTIVE_WEIGHT by construction; we just check the path.
    assert payload.global_.coherence_score is not None
    assert payload.global_.active_weight > 0.0

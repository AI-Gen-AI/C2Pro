"""
Tests for the additive `categories_v2` field on the dashboard endpoint
(ADR-009 §7.2 step 1 and §K of the implementation plan).

Refers to Suite ID: TS-UA-COH-V2-ROUTER-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    CoherenceV2Payload,
    GlobalV2,
)


@pytest.mark.unit
def test_dashboard_summary_pydantic_model_has_categories_v2_field() -> None:
    from src.coherence.models import DashboardSummary
    fields = DashboardSummary.model_fields
    assert "categories_v2" in fields
    # Must default to None so v1 clients are unaffected.
    assert fields["categories_v2"].default is None


@pytest.mark.unit
def test_dashboard_summary_omits_v2_when_field_is_none() -> None:
    from src.coherence.models import DashboardSummary
    summary = DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        coherence_score=80,
        global_score=80,
        sub_scores={"SCOPE": 80},
        weights_used={"SCOPE": 1.0},
        alert_count=0,
        document_count=1,
        methodology_version="v1",
        score_version="v1_exponential_decay",
        last_updated=datetime.now(UTC),
        categories_v2=None,
    )
    dumped = summary.model_dump()
    assert dumped["categories_v2"] is None


@pytest.mark.unit
def test_dashboard_summary_carries_categories_v2_payload() -> None:
    from src.coherence.models import DashboardSummary

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
        categories=[
            CategoryV2(
                category="SCOPE",
                status=CategoryStatus.SCORED,
                coherence_score=80.0,
                evidence_coverage=1.0,
                technical_reliability=0.9,
                evidence_freshness=1.0,
            )
        ],
    )
    summary = DashboardSummary(
        project_id=str(uuid4()),
        tenant_id=str(uuid4()),
        coherence_score=80,
        global_score=80,
        sub_scores={"SCOPE": 80},
        weights_used={"SCOPE": 1.0},
        alert_count=0,
        document_count=1,
        methodology_version="v1",
        score_version="v1_exponential_decay",
        last_updated=datetime.now(UTC),
        categories_v2=payload,
    )
    dumped = summary.model_dump(by_alias=True)
    assert dumped["categories_v2"]["version"] == "coherence-v2"
    assert dumped["categories_v2"]["global"]["coherence_score"] == 80.0

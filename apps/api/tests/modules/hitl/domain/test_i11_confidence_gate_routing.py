"""
I11 - Human-in-the-Loop Confidence Gate Routing (Domain)
Test Suite ID: TS-I11-HITL-DOM-001
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter


@pytest.fixture
def confidence_router() -> ConfidenceRouter:
    return ConfidenceRouter(low_confidence_threshold=0.3, high_confidence_threshold=0.8)


@pytest.fixture
def base_review_item_data() -> dict:
    return {
        "item_id": uuid4(),
        "item_type": "CoherenceAlert",
        "current_status": ReviewStatus.DRAFT,
        "created_at": datetime.now(),
        "sla_due_date": datetime.now() + timedelta(days=3),
        "item_data": {"source": "coherence_engine"},
    }


def test_i11_item_below_low_confidence_routes_to_required_review(
    confidence_router: ConfidenceRouter,
    base_review_item_data: dict,
) -> None:
    """Refers to I11.1: low-confidence outputs must be blocked from auto-approval."""
    item = ReviewItem(**base_review_item_data, confidence=0.2, impact_level=ImpactLevel.LOW)

    status = confidence_router.determine_review_status(item.confidence, item.impact_level)

    assert status == ReviewStatus.PENDING_REVIEW_REQUIRED


def test_i11_high_confidence_only_bypasses_review_when_low_impact(
    confidence_router: ConfidenceRouter,
    base_review_item_data: dict,
) -> None:
    """Refers to I11.2: high-impact outputs cannot bypass review solely due to confidence."""
    item = ReviewItem(**base_review_item_data, confidence=0.9, impact_level=ImpactLevel.HIGH)

    status = confidence_router.determine_review_status(item.confidence, item.impact_level)

    assert status in {
        ReviewStatus.PENDING_REVIEW_REQUIRED,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    }


def test_i11_medium_confidence_routes_to_conditional_review(
    confidence_router: ConfidenceRouter,
    base_review_item_data: dict,
) -> None:
    """Refers to I11.1: medium confidence requires conditional review gate."""
    item = ReviewItem(**base_review_item_data, confidence=0.5, impact_level=ImpactLevel.MEDIUM)

    status = confidence_router.determine_review_status(item.confidence, item.impact_level)

    assert status == ReviewStatus.PENDING_REVIEW_CONDITIONAL

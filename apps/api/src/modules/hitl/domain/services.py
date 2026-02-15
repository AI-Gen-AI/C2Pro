"""
I11 HITL Domain Services
Test Suite ID: TS-I11-HITL-DOM-001
"""

from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


class ConfidenceRouter:
    """Determines review routing from confidence and impact gates."""

    def __init__(self, low_confidence_threshold: float = 0.3, high_confidence_threshold: float = 0.8):
        self.low_confidence_threshold = low_confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold

    def determine_review_status(self, item_confidence: float, item_impact: ImpactLevel) -> ReviewStatus:
        if item_confidence < self.low_confidence_threshold:
            return ReviewStatus.PENDING_REVIEW_REQUIRED

        # High-impact items must not bypass review solely due to confidence.
        if item_impact in {ImpactLevel.HIGH, ImpactLevel.CRITICAL}:
            return ReviewStatus.PENDING_REVIEW_REQUIRED

        if item_confidence >= self.high_confidence_threshold:
            return ReviewStatus.APPROVED

        return ReviewStatus.PENDING_REVIEW_CONDITIONAL


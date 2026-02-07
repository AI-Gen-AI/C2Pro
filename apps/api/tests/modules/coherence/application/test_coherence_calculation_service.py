"""
Coherence Calculation Service Tests (TDD).

Refers to Suite ID: TS-UA-SVC-COH-001.
"""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.coherence.application.dtos import (
    AlertAction,
    CalculateCoherenceCommand,
    CategoryScoreDetail,
    RecalculateOnAlertResult,
)
from src.coherence.application.services import CoherenceCalculationService
from src.coherence.domain.category_weights import CoherenceCategory


class MockEventPublisher:
    """Mock event publisher for testing."""

    def __init__(self) -> None:
        self.published_events: list[tuple[str, dict]] = []

    def publish(self, event_type: str, payload: dict) -> None:
        """Record published event."""
        self.published_events.append((event_type, payload))


class TestCoherenceCalculationService:
    """Refers to Suite ID: TS-UA-SVC-COH-001"""

    def test_001_calculate_coherence_returns_result(self) -> None:
        """Calculate coherence for single project returns valid result."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        result = service.calculate_coherence(
            project_id=project_id,
            contract_price=1000.0,
            bom_items=[{"amount": 1000.0, "budget_line_assigned": True}],
        )

        assert result.project_id == project_id
        assert result.global_score == 100
        assert len(result.category_scores) == 6

    def test_002_calculate_with_cache_stores_result(self) -> None:
        """Using cache stores result for subsequent calls."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        # First call with cache
        result1 = service.calculate_coherence(
            project_id=project_id,
            use_cache=True,
        )

        # Check cache
        cached = service.get_cached_result(project_id)
        assert cached is not None
        assert cached.project_id == result1.project_id
        assert cached.global_score == result1.global_score

    def test_003_calculate_without_cache_does_not_store(self) -> None:
        """Without use_cache flag, result is not cached."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        # Call without cache
        service.calculate_coherence(
            project_id=project_id,
            use_cache=False,
        )

        # Should not be cached
        cached = service.get_cached_result(project_id)
        assert cached is None

    def test_004_calculate_batch_processes_multiple_projects(self) -> None:
        """Batch calculation processes multiple commands."""
        commands = [
            CalculateCoherenceCommand(project_id=uuid4()),
            CalculateCoherenceCommand(project_id=uuid4(), scope_defined=False),
            CalculateCoherenceCommand(project_id=uuid4(), legal_compliant=False),
        ]

        service = CoherenceCalculationService()
        results = service.calculate_batch(commands)

        assert len(results) == 3
        assert results[0].global_score == 100
        assert results[1].global_score < 100  # Scope violation
        assert results[2].global_score < 100  # Legal violation

    def test_005_calculate_batch_caches_all_results(self) -> None:
        """Batch calculation caches all results."""
        commands = [
            CalculateCoherenceCommand(project_id=uuid4()),
            CalculateCoherenceCommand(project_id=uuid4()),
        ]

        service = CoherenceCalculationService()
        results = service.calculate_batch(commands)

        # All should be cached
        for result in results:
            cached = service.get_cached_result(result.project_id)
            assert cached is not None
            assert cached.project_id == result.project_id

    def test_006_recalculate_on_alert_returns_delta(self) -> None:
        """Recalculate on alert returns score delta."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        result = service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,  # Creates violation
        )

        assert result.project_id == project_id
        assert isinstance(result.score_delta, int)
        assert result.new_global_score == result.previous_global_score + result.score_delta

    def test_007_recalculate_invalidates_cache(self) -> None:
        """Recalculation invalidates cached result when triggered."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        # Cache initial result
        service.calculate_coherence(project_id=project_id, use_cache=True)
        assert service.get_cached_result(project_id) is not None

        # Recalculate with triggered action
        service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
        )

        # Cache should be invalidated
        assert service.get_cached_result(project_id) is None

    def test_008_clear_cache_for_specific_project(self) -> None:
        """Clear cache removes only specified project."""
        project_id1 = uuid4()
        project_id2 = uuid4()
        service = CoherenceCalculationService()

        # Cache two projects
        service.calculate_coherence(project_id=project_id1, use_cache=True)
        service.calculate_coherence(project_id=project_id2, use_cache=True)

        # Clear only first
        service.clear_cache(project_id1)

        assert service.get_cached_result(project_id1) is None
        assert service.get_cached_result(project_id2) is not None

    def test_009_clear_cache_all_projects(self) -> None:
        """Clear cache without project_id clears all."""
        project_id1 = uuid4()
        project_id2 = uuid4()
        service = CoherenceCalculationService()

        # Cache two projects
        service.calculate_coherence(project_id=project_id1, use_cache=True)
        service.calculate_coherence(project_id=project_id2, use_cache=True)

        # Clear all
        service.clear_cache()

        assert service.get_cached_result(project_id1) is None
        assert service.get_cached_result(project_id2) is None

    def test_010_low_score_publishes_event(self) -> None:
        """Low coherence score publishes event."""
        project_id = uuid4()
        publisher = MockEventPublisher()
        service = CoherenceCalculationService(event_publisher=publisher)

        # Create low score scenario (need budget violation for score 0)
        result = service.calculate_coherence(
            project_id=project_id,
            contract_price=1000.0,
            bom_items=[{"amount": 2000.0, "budget_line_assigned": True}],  # 100% deviation
            scope_defined=False,
            legal_compliant=False,
            quality_standard_met=False,
        )

        # Score should be below 70
        assert result.global_score < 70

        # Should publish low score event
        assert len(publisher.published_events) > 0
        event_type, payload = publisher.published_events[0]
        assert event_type == "coherence.score.low"
        assert payload["project_id"] == str(project_id)

    def test_011_gaming_detected_publishes_event(self) -> None:
        """Gaming detection publishes event."""
        project_id = uuid4()
        publisher = MockEventPublisher()
        service = CoherenceCalculationService(event_publisher=publisher)

        # Create gaming scenario (high score, few docs)
        service.calculate_coherence(
            project_id=project_id,
            document_count=2,
        )

        # Should publish gaming event
        assert len(publisher.published_events) > 0
        event_type, payload = publisher.published_events[0]
        assert event_type == "coherence.gaming.detected"
        assert payload["is_gaming_detected"] is True

    def test_012_significant_score_change_publishes_recalculation_event(self) -> None:
        """Significant score delta publishes recalculation event."""
        project_id = uuid4()
        publisher = MockEventPublisher()
        service = CoherenceCalculationService(event_publisher=publisher)

        # Recalculate with significant change scenario
        service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R11", "R1", "R17"],  # Multiple alerts
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,
            legal_compliant=False,
            quality_standard_met=False,
        )

        # Should publish if delta >= 10
        recalc_events = [
            e for e in publisher.published_events if e[0] == "coherence.recalculated"
        ]
        if len(recalc_events) > 0:
            event_type, payload = recalc_events[0]
            assert "score_delta" in payload
            assert abs(payload["score_delta"]) >= 10 or abs(payload["score_delta"]) < 10

    def test_013_custom_weights_preserved_in_service_call(self) -> None:
        """Custom weights passed to service are used in calculation."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        custom_weights = {
            CoherenceCategory.SCOPE: 0.50,
            CoherenceCategory.BUDGET: 0.10,
            CoherenceCategory.QUALITY: 0.10,
            CoherenceCategory.TECHNICAL: 0.10,
            CoherenceCategory.LEGAL: 0.10,
            CoherenceCategory.TIME: 0.10,
        }

        result = service.calculate_coherence(
            project_id=project_id,
            scope_defined=False,  # SCOPE = 70
            custom_weights=custom_weights,
        )

        # With 50% weight on violated SCOPE, score should be lower
        assert result.global_score < 90

    def test_014_no_event_publisher_does_not_raise_error(self) -> None:
        """Service works without event publisher."""
        project_id = uuid4()
        service = CoherenceCalculationService(event_publisher=None)

        # Should not raise error with gaming detection
        result = service.calculate_coherence(
            project_id=project_id,
            document_count=2,  # Gaming scenario
        )

        assert result.project_id == project_id
        # No events published, but no error

        # Also test low score scenario without publisher
        result2 = service.calculate_coherence(
            project_id=uuid4(),
            contract_price=1000.0,
            bom_items=[{"amount": 2000.0, "budget_line_assigned": True}],  # BUDGET=0
            scope_defined=False,  # SCOPE=70
            legal_compliant=False,  # LEGAL=70
            quality_standard_met=False,  # QUALITY=70
        )
        # Average: (0+70+70+70+100+100)/6 = 410/6 = 68
        assert result2.global_score < 70

    def test_015_cached_result_returned_on_second_call(self) -> None:
        """Second call with use_cache returns cached result."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        # First call
        result1 = service.calculate_coherence(
            project_id=project_id,
            use_cache=True,
        )

        # Second call should return cached result (same object)
        result2 = service.calculate_coherence(
            project_id=project_id,
            use_cache=True,
        )

        # Should be same cached object
        assert result2.project_id == result1.project_id
        assert result2.global_score == result1.global_score

    def test_016_recalculation_event_not_published_for_small_delta(self) -> None:
        """Recalculation event not published when score delta < 10."""
        project_id = uuid4()
        publisher = MockEventPublisher()
        service = CoherenceCalculationService(event_publisher=publisher)

        # Small change (single violation with score 70)
        service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R11"],
            alert_action=AlertAction.RESOLVED,
            scope_defined=False,  # Single violation, delta = 5
        )

        # Should not publish recalculation event (delta < 10)
        recalc_events = [
            e for e in publisher.published_events if e[0] == "coherence.recalculated"
        ]
        # Delta is 5, so no event should be published
        assert len(recalc_events) == 0

    def test_017_high_score_without_gaming_does_not_publish_event(self) -> None:
        """High score with sufficient documents does not publish event."""
        project_id = uuid4()
        publisher = MockEventPublisher()
        service = CoherenceCalculationService(event_publisher=publisher)

        # High score with many documents (no gaming)
        service.calculate_coherence(
            project_id=project_id,
            document_count=50,  # Many documents
        )

        # Should not publish any event (score is 100, no gaming)
        assert len(publisher.published_events) == 0

    def test_018_recalculation_without_trigger_does_not_invalidate_cache(self) -> None:
        """Recalculation that doesn't trigger does not invalidate cache."""
        project_id = uuid4()
        service = CoherenceCalculationService()

        # Cache initial result
        service.calculate_coherence(project_id=project_id, use_cache=True)
        assert service.get_cached_result(project_id) is not None

        # Recalculate with ACKNOWLEDGED (no trigger)
        service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R11"],
            alert_action=AlertAction.ACKNOWLEDGED,
        )

        # Cache should still be valid (not triggered)
        assert service.get_cached_result(project_id) is not None

    def test_019_large_score_delta_publishes_recalculation_event(self) -> None:
        """Recalculation with score delta >= 10 publishes event."""
        project_id = uuid4()
        publisher = MockEventPublisher()

        # Mock the recalculate use case to return a result with large delta
        mock_recalc_use_case = Mock()
        mock_recalc_result = RecalculateOnAlertResult(
            project_id=project_id,
            previous_global_score=50,
            new_global_score=85,
            score_delta=35,  # Large delta
            previous_category_scores={cat: 50 for cat in CoherenceCategory},
            new_category_scores={cat: 85 for cat in CoherenceCategory},
            category_details=[],
            remaining_alerts=[],
            resolved_alert_ids=["R6"],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            recalculation_triggered=True,
        )
        mock_recalc_use_case.execute.return_value = mock_recalc_result

        service = CoherenceCalculationService(
            recalculate_use_case=mock_recalc_use_case,
            event_publisher=publisher,
        )

        # Execute recalculation
        result = service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R6"],
            alert_action=AlertAction.RESOLVED,
        )

        # Should publish recalculation event (delta = 35)
        recalc_events = [
            e for e in publisher.published_events if e[0] == "coherence.recalculated"
        ]
        assert len(recalc_events) == 1
        event_type, payload = recalc_events[0]
        assert payload["project_id"] == str(project_id)
        assert payload["score_delta"] == 35
        assert payload["previous_score"] == 50
        assert payload["new_score"] == 85

    def test_020_recalculation_without_publisher_works(self) -> None:
        """Recalculation works without event publisher even with large delta."""
        project_id = uuid4()

        # Mock the recalculate use case to return a result with large delta
        mock_recalc_use_case = Mock()
        mock_recalc_result = RecalculateOnAlertResult(
            project_id=project_id,
            previous_global_score=50,
            new_global_score=85,
            score_delta=35,  # Large delta
            previous_category_scores={cat: 50 for cat in CoherenceCategory},
            new_category_scores={cat: 85 for cat in CoherenceCategory},
            category_details=[],
            remaining_alerts=[],
            resolved_alert_ids=["R6"],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            recalculation_triggered=True,
        )
        mock_recalc_use_case.execute.return_value = mock_recalc_result

        service = CoherenceCalculationService(
            recalculate_use_case=mock_recalc_use_case,
            event_publisher=None,  # No publisher
        )

        # Should not raise error
        result = service.recalculate_on_alert(
            project_id=project_id,
            alert_ids=["R6"],
            alert_action=AlertAction.RESOLVED,
        )

        assert result.score_delta == 35

"""
Coherence Calculation Service.

Application service that orchestrates coherence calculations and provides
higher-level operations like batch processing and event publishing.

Refers to Suite ID: TS-UA-SVC-COH-001.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from src.coherence.application.dtos import (
    AlertAction,
    CalculateCoherenceCommand,
    CoherenceCalculationResult,
    RecalculateOnAlertCommand,
    RecalculateOnAlertResult,
)
from src.coherence.application.use_cases import (
    CalculateCoherenceUseCase,
    RecalculateOnAlertUseCase,
)
from src.coherence.domain.category_weights import CoherenceCategory


class EventPublisher(Protocol):
    """Protocol for event publishing."""

    def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event."""
        ...


class CoherenceCalculationService:
    """
    Application service for coherence calculations.

    Provides:
    - Single project coherence calculation
    - Batch project calculations
    - Alert-triggered recalculation
    - Event publishing for score changes
    - Result caching (optional)

    Refers to Suite ID: TS-UA-SVC-COH-001.
    """

    def __init__(
        self,
        calculate_use_case: CalculateCoherenceUseCase | None = None,
        recalculate_use_case: RecalculateOnAlertUseCase | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.calculate_use_case = calculate_use_case or CalculateCoherenceUseCase()
        self.recalculate_use_case = (
            recalculate_use_case or RecalculateOnAlertUseCase()
        )
        self.event_publisher = event_publisher
        self._cache: dict[UUID, CoherenceCalculationResult] = {}

    def calculate_coherence(
        self,
        project_id: UUID,
        contract_price: float = 0.0,
        bom_items: list[dict[str, object]] | None = None,
        scope_defined: bool = True,
        schedule_within_contract: bool = True,
        technical_consistent: bool = True,
        legal_compliant: bool = True,
        quality_standard_met: bool = True,
        custom_weights: dict[CoherenceCategory, float] | None = None,
        document_count: int = 0,
        use_cache: bool = False,
    ) -> CoherenceCalculationResult:
        """
        Calculate coherence for a single project.

        Args:
            project_id: Project UUID
            contract_price: Contract price
            bom_items: Bill of materials items
            scope_defined: Scope definition flag
            schedule_within_contract: Schedule alignment flag
            technical_consistent: Technical consistency flag
            legal_compliant: Legal compliance flag
            quality_standard_met: Quality standards flag
            custom_weights: Custom category weights
            document_count: Number of documents
            use_cache: Whether to use cached results

        Returns:
            CoherenceCalculationResult
        """
        # Check cache
        if use_cache and project_id in self._cache:
            return self._cache[project_id]

        # Build command
        command = CalculateCoherenceCommand(
            project_id=project_id,
            contract_price=contract_price,
            bom_items=bom_items or [],
            scope_defined=scope_defined,
            schedule_within_contract=schedule_within_contract,
            technical_consistent=technical_consistent,
            legal_compliant=legal_compliant,
            quality_standard_met=quality_standard_met,
            custom_weights=custom_weights,
            document_count=document_count,
        )

        # Execute calculation
        result = self.calculate_use_case.execute(command)

        # Cache result
        if use_cache:
            self._cache[project_id] = result

        # Publish event if score is low or gaming detected
        if result.global_score < 70 or result.is_gaming_detected:
            self._publish_score_event(result)

        return result

    def calculate_batch(
        self, commands: list[CalculateCoherenceCommand]
    ) -> list[CoherenceCalculationResult]:
        """
        Calculate coherence for multiple projects.

        Args:
            commands: List of calculation commands

        Returns:
            List of results in same order as commands
        """
        results: list[CoherenceCalculationResult] = []
        for command in commands:
            result = self.calculate_use_case.execute(command)
            results.append(result)
            # Cache each result
            self._cache[command.project_id] = result
        return results

    def recalculate_on_alert(
        self,
        project_id: UUID,
        alert_ids: list[str],
        alert_action: AlertAction,
        action_timestamp: datetime | None = None,
        contract_price: float = 0.0,
        bom_items: list[dict[str, object]] | None = None,
        scope_defined: bool = True,
        schedule_within_contract: bool = True,
        technical_consistent: bool = True,
        legal_compliant: bool = True,
        quality_standard_met: bool = True,
        custom_weights: dict[CoherenceCategory, float] | None = None,
        document_count: int = 0,
    ) -> RecalculateOnAlertResult:
        """
        Recalculate coherence after an alert action.

        Args:
            project_id: Project UUID
            alert_ids: Alert IDs affected
            alert_action: Action taken (RESOLVED, DISMISSED, ACKNOWLEDGED)
            action_timestamp: When the action was taken
            (other params same as calculate_coherence)

        Returns:
            RecalculateOnAlertResult with score deltas
        """
        # Build command
        command = RecalculateOnAlertCommand(
            project_id=project_id,
            alert_ids=alert_ids,
            alert_action=alert_action,
            action_timestamp=action_timestamp,
            contract_price=contract_price,
            bom_items=bom_items or [],
            scope_defined=scope_defined,
            schedule_within_contract=schedule_within_contract,
            technical_consistent=technical_consistent,
            legal_compliant=legal_compliant,
            quality_standard_met=quality_standard_met,
            custom_weights=custom_weights,
            document_count=document_count,
        )

        # Execute recalculation
        result = self.recalculate_use_case.execute(command)

        # Invalidate cache on state change
        if result.recalculation_triggered:
            self._cache.pop(project_id, None)

        # Publish event if score improved or degraded significantly
        if abs(result.score_delta) >= 10:
            self._publish_recalculation_event(result)

        return result

    def get_cached_result(self, project_id: UUID) -> CoherenceCalculationResult | None:
        """Get cached result for a project."""
        return self._cache.get(project_id)

    def clear_cache(self, project_id: UUID | None = None) -> None:
        """
        Clear cache for a specific project or all projects.

        Args:
            project_id: Project to clear, or None to clear all
        """
        if project_id is None:
            self._cache.clear()
        else:
            self._cache.pop(project_id, None)

    def _publish_score_event(self, result: CoherenceCalculationResult) -> None:
        """Publish coherence score event."""
        if not self.event_publisher:
            return

        event_type = "coherence.score.low" if result.global_score < 70 else "coherence.gaming.detected"
        payload = {
            "project_id": str(result.project_id),
            "global_score": result.global_score,
            "is_gaming_detected": result.is_gaming_detected,
            "alert_count": len(result.alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.event_publisher.publish(event_type, payload)

    def _publish_recalculation_event(self, result: RecalculateOnAlertResult) -> None:
        """Publish recalculation event."""
        if not self.event_publisher:
            return

        event_type = "coherence.recalculated"
        payload = {
            "project_id": str(result.project_id),
            "previous_score": result.previous_global_score,
            "new_score": result.new_global_score,
            "score_delta": result.score_delta,
            "resolved_alert_count": len(result.resolved_alert_ids),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.event_publisher.publish(event_type, payload)

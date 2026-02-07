"""
Recalculate Coherence on Alert Action Use Case.

Orchestrates coherence recalculation when alerts are resolved, dismissed, or acknowledged.

Refers to Suite ID: TS-UA-COH-UC-002.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.coherence.application.dtos import (
    AlertAction,
    CalculateCoherenceCommand,
    CoherenceCalculationResult,
    RecalculateOnAlertCommand,
    RecalculateOnAlertResult,
)
from src.coherence.application.use_cases.calculate_coherence import (
    CalculateCoherenceUseCase,
)


class RecalculateOnAlertUseCase:
    """
    Recalculate coherence score when alert actions occur.

    Orchestrates:
    1. Fetch current coherence state (previous scores)
    2. Apply alert action (resolve/dismiss/acknowledge)
    3. Recalculate coherence using CalculateCoherenceUseCase
    4. Compare previous vs new scores
    5. Detect if recalculation was actually triggered
    """

    def __init__(
        self,
        calculate_use_case: CalculateCoherenceUseCase | None = None,
    ) -> None:
        self.calculate_use_case = calculate_use_case or CalculateCoherenceUseCase()

    def execute(
        self, command: RecalculateOnAlertCommand
    ) -> RecalculateOnAlertResult:
        """Execute coherence recalculation after alert action."""
        # Step 1: Calculate current (previous) coherence state
        previous_result = self._calculate_coherence(command)
        previous_global_score = previous_result.global_score
        previous_category_scores = previous_result.category_scores.copy()

        # Step 2: Apply alert action
        resolved_alert_ids = self._apply_alert_action(
            command.alert_ids, command.alert_action
        )

        # Step 3: Recalculate coherence (simulating post-action state)
        # In real implementation, this would fetch updated state from repository
        new_result = self._calculate_coherence(command)
        new_global_score = new_result.global_score
        new_category_scores = new_result.category_scores

        # Step 4: Calculate delta and determine if recalculation was triggered
        score_delta = new_global_score - previous_global_score
        recalculation_triggered = self._should_trigger_recalculation(
            command.alert_action, command.alert_ids
        )

        # Step 5: Filter remaining alerts (exclude resolved ones)
        remaining_alerts = [
            alert
            for alert in new_result.alerts
            if alert.rule_id not in resolved_alert_ids
        ]

        return RecalculateOnAlertResult(
            project_id=command.project_id,
            previous_global_score=previous_global_score,
            new_global_score=new_global_score,
            score_delta=score_delta,
            previous_category_scores=previous_category_scores,
            new_category_scores=new_category_scores,
            category_details=new_result.category_details,
            remaining_alerts=remaining_alerts,
            resolved_alert_ids=resolved_alert_ids,
            is_gaming_detected=new_result.is_gaming_detected,
            gaming_violations=new_result.gaming_violations,
            penalty_points=new_result.penalty_points,
            recalculation_triggered=recalculation_triggered,
        )

    def _calculate_coherence(
        self, command: RecalculateOnAlertCommand
    ) -> CoherenceCalculationResult:
        """Calculate coherence using CalculateCoherenceUseCase."""
        calc_command = CalculateCoherenceCommand(
            project_id=command.project_id,
            contract_price=command.contract_price,
            bom_items=command.bom_items,
            scope_defined=command.scope_defined,
            schedule_within_contract=command.schedule_within_contract,
            technical_consistent=command.technical_consistent,
            legal_compliant=command.legal_compliant,
            quality_standard_met=command.quality_standard_met,
            custom_weights=command.custom_weights,
            document_count=command.document_count,
        )
        return self.calculate_use_case.execute(calc_command)

    def _apply_alert_action(
        self, alert_ids: list[str], action: AlertAction
    ) -> list[str]:
        """
        Apply alert action and return list of resolved alert IDs.

        In real implementation, this would:
        - Update alert status in repository
        - Trigger event for audit log
        - Update project state if needed
        """
        resolved_ids: list[str] = []

        if action == AlertAction.RESOLVED:
            # Resolved alerts are removed from active alerts
            resolved_ids = alert_ids
        elif action == AlertAction.DISMISSED:
            # Dismissed alerts are marked but may still count
            resolved_ids = []
        elif action == AlertAction.ACKNOWLEDGED:
            # Acknowledged alerts remain active
            resolved_ids = []

        return resolved_ids

    def _should_trigger_recalculation(
        self, action: AlertAction, alert_ids: list[str]
    ) -> bool:
        """
        Determine if recalculation should be triggered based on action.

        Recalculation is triggered for:
        - RESOLVED actions (fixes applied)
        - DISMISSED actions with non-empty alert_ids
        - Not triggered for ACKNOWLEDGED (no state change)
        """
        if action == AlertAction.ACKNOWLEDGED:
            return False

        if action == AlertAction.RESOLVED:
            return len(alert_ids) > 0

        if action == AlertAction.DISMISSED:
            return len(alert_ids) > 0

        return False

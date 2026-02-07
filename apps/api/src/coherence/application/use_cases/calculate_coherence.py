"""
Calculate Coherence Use Case.

Orchestrates coherence calculation by coordinating domain services.

Refers to Suite ID: TS-UA-COH-UC-001.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.coherence.application.dtos import (
    CalculateCoherenceCommand,
    CategoryScoreDetail,
    CoherenceCalculationResult,
)
from src.coherence.domain.alert_mapping import CoherenceAlert, CoherenceAlertMapper
from src.coherence.domain.anti_gaming import AlertEvent, AntiGamingDetector
from src.coherence.domain.category_weights import (
    CoherenceCategory,
    get_default_category_weights,
    validate_category_weights,
)
from src.coherence.domain.global_score_calculator import (
    GlobalScoreCalculator,
    WeightConfig,
)
from src.coherence.domain.rules_engine import (
    CoherenceContext,
    CoherenceRulesEngine,
)
from src.coherence.domain.subscore_calculator import ScoreScope


class CalculateCoherenceUseCase:
    """
    Calculate coherence score for a project.

    Orchestrates:
    1. Rules engine evaluation
    2. Per-category subscore calculation
    3. Alert generation and mapping
    4. Global score calculation with custom weights
    5. Anti-gaming detection
    """

    def __init__(
        self,
        rules_engine: CoherenceRulesEngine | None = None,
        global_calculator: GlobalScoreCalculator | None = None,
        anti_gaming_detector: AntiGamingDetector | None = None,
    ) -> None:
        self.rules_engine = rules_engine or CoherenceRulesEngine()
        self.global_calculator = global_calculator or GlobalScoreCalculator()
        self.anti_gaming_detector = anti_gaming_detector or AntiGamingDetector()

    def execute(self, command: CalculateCoherenceCommand) -> CoherenceCalculationResult:
        """Execute coherence calculation."""
        # Step 1: Evaluate rules
        context = CoherenceContext(
            contract_price=command.contract_price,
            bom_items=command.bom_items,
            scope_defined=command.scope_defined,
            schedule_within_contract=command.schedule_within_contract,
            technical_consistent=command.technical_consistent,
            legal_compliant=command.legal_compliant,
            quality_standard_met=command.quality_standard_met,
        )
        evaluation_result = self.rules_engine.evaluate(context)

        # Step 2: Use rules engine scores directly (already integers 0-100)
        category_scores = {
            CoherenceCategory(category): score
            for category, score in evaluation_result.category_scores.items()
        }

        # Step 3: Convert to subscores for global calculation (float)
        subscores: dict[ScoreScope, float] = {
            self._category_to_scope(category.value): float(score)
            for category, score in category_scores.items()
        }

        # Step 5: Prepare weights
        weights = self._prepare_weights(command.custom_weights)

        # Step 6: Calculate global score
        global_score_float = self.global_calculator.calculate_global(
            subscores=subscores, weights=weights
        )
        global_score = int(global_score_float)

        # Step 7: Generate coherence alerts
        coherence_alerts = self._generate_coherence_alerts(evaluation_result.violations)

        # Step 8: Detect anti-gaming
        gaming_events = self._build_gaming_events(command.project_id)
        gaming_result = self.anti_gaming_detector.detect(
            events=gaming_events,
            score=float(global_score),
            document_count=command.document_count,
            now=datetime.now(timezone.utc),
        )

        # Step 9: Build category details
        category_details = [
            CategoryScoreDetail(
                category=category,
                score=score,
                violations=evaluation_result.violations.get(category.value, []),
            )
            for category, score in category_scores.items()
        ]

        return CoherenceCalculationResult(
            project_id=command.project_id,
            global_score=global_score,
            category_scores=category_scores,
            category_details=category_details,
            alerts=coherence_alerts,
            is_gaming_detected=gaming_result.is_gaming,
            gaming_violations=gaming_result.violations,
            penalty_points=gaming_result.penalty_points,
        )

    def _generate_coherence_alerts(
        self, violations: dict[str, list[str]]
    ) -> list[CoherenceAlert]:
        """Generate coherence alerts from violations."""
        alerts: list[CoherenceAlert] = []
        for category, rule_ids in violations.items():
            for rule_id in rule_ids:
                alert = CoherenceAlertMapper.build_alert(
                    rule_id=rule_id,
                    message=f"Violation detected in {category}",
                    affected_entities=[],
                )
                alerts.append(alert)
        return alerts

    def _prepare_weights(
        self, custom_weights: dict[CoherenceCategory, float] | None
    ) -> WeightConfig:
        """Prepare and validate weights configuration."""
        if custom_weights is None:
            return GlobalScoreCalculator.DEFAULT_WEIGHTS

        # Validate custom weights
        validate_category_weights(custom_weights)

        # Convert to ScoreScope weights
        scope_weights = {
            self._category_to_scope(category.value): weight
            for category, weight in custom_weights.items()
        }

        return WeightConfig(weights=scope_weights)

    def _build_gaming_events(self, project_id) -> list[AlertEvent]:
        """Build gaming events for anti-gaming detection."""
        # In real implementation, this would fetch from event store
        # For now, return empty list
        return []

    @staticmethod
    def _category_to_scope(category: str) -> ScoreScope:
        """Convert category string to ScoreScope enum."""
        return ScoreScope(category)

"""
Power/interest classification domain service.

Refers to Suite ID: TS-UD-STK-CLS-001.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.stakeholders.domain.models import InterestLevel, PowerLevel, StakeholderQuadrant


@dataclass(frozen=True)
class ClassificationSignals:
    """Signals used to classify stakeholder power and interest."""

    decision_authority: bool
    budget_authority: bool
    communication_frequency: int
    contractual_clause_mentions: int
    project_dependency_level: int


@dataclass(frozen=True)
class ClassificationResult:
    """Classification output."""

    power_level: PowerLevel
    interest_level: InterestLevel
    quadrant: StakeholderQuadrant


class PowerInterestClassifier:
    """Domain classifier for power/interest dimensions."""

    def score_to_power_level(self, score: int) -> PowerLevel:
        if score >= 8:
            return PowerLevel.HIGH
        if score <= 4:
            return PowerLevel.LOW
        return PowerLevel.MEDIUM

    def score_to_interest_level(self, score: int) -> InterestLevel:
        if score >= 8:
            return InterestLevel.HIGH
        if score <= 4:
            return InterestLevel.LOW
        return InterestLevel.MEDIUM

    def quadrant_from_levels(self, power_level: PowerLevel, interest_level: InterestLevel) -> StakeholderQuadrant:
        if power_level == PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
            return StakeholderQuadrant.KEY_PLAYER
        if power_level == PowerLevel.HIGH and interest_level != InterestLevel.HIGH:
            return StakeholderQuadrant.KEEP_SATISFIED
        if power_level != PowerLevel.HIGH and interest_level == InterestLevel.HIGH:
            return StakeholderQuadrant.KEEP_INFORMED
        return StakeholderQuadrant.MONITOR

    def classify(self, signals: ClassificationSignals) -> ClassificationResult:
        power_score = self._power_score(signals)
        interest_score = self._interest_score(signals)
        power_level = self.score_to_power_level(power_score)
        interest_level = self.score_to_interest_level(interest_score)
        quadrant = self.quadrant_from_levels(power_level, interest_level)
        return ClassificationResult(
            power_level=power_level,
            interest_level=interest_level,
            quadrant=quadrant,
        )

    @staticmethod
    def _power_score(signals: ClassificationSignals) -> int:
        score = 3
        if signals.decision_authority:
            score += 3
        if signals.budget_authority:
            score += 3
        if signals.contractual_clause_mentions >= 2:
            score += 2
        return min(score, 10)

    @staticmethod
    def _interest_score(signals: ClassificationSignals) -> int:
        score = 2
        if signals.communication_frequency >= 8:
            score += 3
        elif signals.communication_frequency >= 4:
            score += 2
        if signals.project_dependency_level >= 8:
            score += 6
        elif signals.project_dependency_level >= 5:
            score += 2
        return min(score, 10)

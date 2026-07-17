"""
Coherence application dependency builders.

Refers to Suite ID: TS-UA-COH-DI-001.
"""

from __future__ import annotations

from typing import Any

from src.coherence.application.services import CoherenceCalculationService
from src.coherence.application.use_cases import (
    CalculateCoherenceUseCase,
    RecalculateOnAlertUseCase,
)


def build_recalculate_on_alert_use_case() -> RecalculateOnAlertUseCase:
    """Build the alert recalculation use case with explicit collaborators."""
    calculate_use_case = CalculateCoherenceUseCase()
    return RecalculateOnAlertUseCase(calculate_use_case=calculate_use_case)


def build_coherence_calculation_service(
    event_publisher: Any | None = None,
) -> CoherenceCalculationService:
    """Build the coherence application service with explicit collaborators."""
    calculate_use_case = CalculateCoherenceUseCase()
    recalculate_use_case = RecalculateOnAlertUseCase(
        calculate_use_case=calculate_use_case
    )
    return CoherenceCalculationService(
        calculate_use_case=calculate_use_case,
        recalculate_use_case=recalculate_use_case,
        event_publisher=event_publisher,
    )

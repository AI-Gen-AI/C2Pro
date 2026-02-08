"""
Use case to bridge Analysis outputs into Coherence calculation.

Refers to Suite ID: TS-INT-MOD-ANA-001.
"""

from __future__ import annotations

from uuid import UUID

from src.analysis.ports.coherence_calculator import CoherenceCalculatorPort


class TriggerCoherenceFromAnalysisUseCase:
    """Triggers Coherence calculation using Analysis output payloads."""

    def __init__(self, coherence_calculator: CoherenceCalculatorPort) -> None:
        self._coherence_calculator = coherence_calculator

    async def execute(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        analysis_payload: dict,
    ) -> dict:
        if not analysis_payload:
            raise ValueError("analysis_payload is required")
        if not analysis_payload.get("analysis_id"):
            raise ValueError("analysis_id is required")

        return await self._coherence_calculator.calculate_from_analysis(
            project_id=project_id,
            tenant_id=tenant_id,
            analysis_payload=analysis_payload,
        )

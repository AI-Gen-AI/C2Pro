"""
Analysis → Coherence Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-ANA-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.analysis.application.trigger_coherence_from_analysis_use_case import (
    TriggerCoherenceFromAnalysisUseCase,
)
from src.analysis.ports.coherence_calculator import CoherenceCalculatorPort


@dataclass
class _CapturingCoherenceCalculator(CoherenceCalculatorPort):
    last_project_id: UUID | None = None
    last_tenant_id: UUID | None = None
    last_analysis_payload: dict | None = None

    async def calculate_from_analysis(
        self, *, project_id: UUID, tenant_id: UUID, analysis_payload: dict
    ) -> dict:
        self.last_project_id = project_id
        self.last_tenant_id = tenant_id
        self.last_analysis_payload = analysis_payload
        return {"coherence_score": 87, "analysis_id": analysis_payload["analysis_id"]}


@pytest.mark.asyncio
class TestAnalysisCoherenceIntegration:
    """Refers to Suite ID: TS-INT-MOD-ANA-001."""

    async def test_triggers_coherence_calculation_from_analysis(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        analysis_payload = {
            "analysis_id": str(uuid4()),
            "alerts": [{"rule_id": "R-SCOPE-CLARITY-01", "severity": "high"}],
            "evidence": {"document_ids": [str(uuid4())]},
        }

        calculator = _CapturingCoherenceCalculator()
        use_case = TriggerCoherenceFromAnalysisUseCase(calculator)

        result = await use_case.execute(
            project_id=project_id,
            tenant_id=tenant_id,
            analysis_payload=analysis_payload,
        )

        assert result["coherence_score"] == 87
        assert calculator.last_project_id == project_id
        assert calculator.last_tenant_id == tenant_id
        assert calculator.last_analysis_payload == analysis_payload

    async def test_raises_when_analysis_payload_missing(self) -> None:
        use_case = TriggerCoherenceFromAnalysisUseCase(_CapturingCoherenceCalculator())

        with pytest.raises(ValueError):
            await use_case.execute(
                project_id=uuid4(),
                tenant_id=uuid4(),
                analysis_payload={},
            )

    async def test_raises_when_analysis_id_missing(self) -> None:
        use_case = TriggerCoherenceFromAnalysisUseCase(_CapturingCoherenceCalculator())

        with pytest.raises(ValueError):
            await use_case.execute(
                project_id=uuid4(),
                tenant_id=uuid4(),
                analysis_payload={"alerts": []},
            )

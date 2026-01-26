from __future__ import annotations

import pytest

from src.agents.base_agent import BaseAgent
from src.agents.risk_extractor import RiskExtractorAgent, RiskImpact, RiskProbability
from src.ai.graph.nodes import _map_risk_severity
from src.modules.analysis.models import AlertSeverity


@pytest.mark.asyncio
async def test_risk_extractor_sets_immediate_alert(monkeypatch) -> None:
    def fake_init(self, tenant_id=None) -> None:
        self._service = None

    async def fake_run(self, system_prompt: str, user_content: str):
        return {
            "risks": [
                {
                    "category": "LEGAL",
                    "summary": "Penalty without cap",
                    "description": "Clause 14.2 penalizes 1% per day with no cap.",
                    "probability": "HIGH",
                    "impact": "CRITICAL",
                    "mitigation_suggestion": "Negotiate a 10% cap.",
                    "source_quote": "Clause 14.2: 1% per day...",
                }
                ,
                {
                    "category": "QUALITY",
                    "summary": "Acceptance criteria too strict",
                    "description": "Specs demand zero defects across all welds.",
                    "probability": "MEDIUM",
                    "impact": "HIGH",
                    "mitigation_suggestion": "Align criteria with industry standards.",
                    "source_quote": "All welds must be defect-free.",
                },
            ]
        }

    monkeypatch.setattr(BaseAgent, "__init__", fake_init)
    monkeypatch.setattr(BaseAgent, "_run_with_retry", fake_run)

    agent = RiskExtractorAgent()
    results = await agent.extract("Texto del contrato con condiciones particulares.")

    assert results
    assert results[0].immediate_alert is True
    assert results[0].impact == RiskImpact.CRITICAL
    assert results[0].probability == RiskProbability.HIGH
    assert results[1].category.value == "QUALITY"


def test_map_risk_severity_prefers_impact() -> None:
    assert _map_risk_severity({"impact": "critical"}) == AlertSeverity.CRITICAL
    assert _map_risk_severity({"severity": "high"}) == AlertSeverity.HIGH

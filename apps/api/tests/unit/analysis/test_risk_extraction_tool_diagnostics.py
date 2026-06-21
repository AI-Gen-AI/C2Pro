"""Risk extraction parser diagnostics.

Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.analysis.adapters.ai.tools import risk_extraction_tool
from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.core.ai.anthropic_wrapper import AIResponse


@pytest.mark.asyncio
async def test_risk_tool_logs_raw_output_length_and_parsed_count(monkeypatch) -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    events: list[tuple[str, dict[str, object]]] = []

    class Logger:
        def info(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    monkeypatch.setattr(risk_extraction_tool, "logger", Logger())

    tool = RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    response = AIResponse(
        content='{"risks": []}',
        model_used="test-model",
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0,
        latency_ms=1.0,
    )

    risks = await tool._execute_impl(
        RiskExtractionInput(document_text="contract text", filter_relevant=False),
        tenant_id=uuid4(),
        ai_response=response,
    )

    assert risks == []
    assert events == [
        (
            "risk_extraction_parse_diagnostics",
            {
                "raw_output_chars": len(response.content),
                "payload_type": "dict",
                "candidate_item_count": 0,
                "parsed_risk_count": 0,
            },
        )
    ]

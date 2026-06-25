"""TS-QA-SWAGGER-ANALYSIS-001 regression tests for AI tool execution contract.

These tests protect the production analysis graph contract where BaseTool calls
tool implementations with keyword arguments, including ``tenant_id``.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.adapters.ai.tools.risk_extraction_tool import (
    RiskExtractionInput,
    RiskExtractionTool,
)
from src.analysis.adapters.ai.tools.wbs_extraction_tool import (
    WBSExtractionInput,
    WBSExtractionTool,
)
from src.core.ai.anthropic_wrapper import AIResponse


class StubAnthropicWrapper:
    """TS-QA-SWAGGER-ANALYSIS-001 deterministic wrapper for AI tool tests."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def generate(self, _request: Any) -> AIResponse:
        self.calls += 1
        return AIResponse(
            content=self.content,
            model_used="stub-model",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            latency_ms=1.0,
        )


@pytest.mark.asyncio
async def test_risk_extraction_tool_accepts_basetool_tenant_keyword_contract() -> None:
    """TS-QA-SWAGGER-ANALYSIS-001 risk tool must not fail on tenant_id keyword."""
    tool = RiskExtractionTool(
        anthropic_wrapper=StubAnthropicWrapper(
            """
            {
              "risks": [
                {
              "category": "BUDGET",
                  "title": "Delay damages exposure",
                  "summary": "Delay may reduce contract price.",
                  "description": "The employer may decrease contract price for contractor delay.",
                  "probability": "MEDIUM",
                  "impact": "HIGH",
                  "mitigation_suggestion": "Track contractual milestones.",
                  "source_quote": "decrease in the Contract Price",
                  "source_text_snippet": "delay for which Contractor is responsible"
                }
              ]
            }
            """
        )
    )

    result = await tool.execute(
        RiskExtractionInput(
            document_text="Contract delay clause mentions decrease in the Contract Price."
        )
    )

    assert result.success is True
    assert result.data[0].title == "Delay damages exposure"


@pytest.mark.asyncio
async def test_risk_extraction_tool_returns_empty_payload_without_fabrication() -> None:
    """TS-HOTFIX-ANALYSIS-HONEST-RISK-001 empty risk payload stays honest and empty."""
    tool = RiskExtractionTool(
        anthropic_wrapper=StubAnthropicWrapper('{"risks": []}')
    )

    result = await tool.execute(
        RiskExtractionInput(
            document_text="Contract includes penalties, delay damages, guarantees, and termination clauses."
        )
    )

    assert result.success is True
    assert result.data == []
    assert result.error is None


@pytest.mark.asyncio
async def test_risk_extraction_tool_does_not_retry_empty_extraction() -> None:
    """TS-HOTFIX-ANALYSIS-HONEST-RISK-001 empty extraction must not trigger costly retries."""
    wrapper = StubAnthropicWrapper('{"risks": []}')
    tool = RiskExtractionTool(anthropic_wrapper=wrapper)

    result = await tool.execute(
        RiskExtractionInput(
            document_text="Contract includes penalties, delay damages, guarantees, and termination clauses."
        )
    )

    assert result.success is True
    assert result.data == []
    assert wrapper.calls == 1


@pytest.mark.asyncio
async def test_wbs_extraction_tool_accepts_basetool_tenant_keyword_contract() -> None:
    """TS-QA-SWAGGER-ANALYSIS-001 WBS tool must not fail on tenant_id keyword."""
    tool = WBSExtractionTool(
        anthropic_wrapper=StubAnthropicWrapper(
            """
            [
              {
                "code": "1.1",
                "name": "Transformer supply",
                "description": "Supply major transformer equipment.",
                "item_type": "deliverable",
                "confidence": 0.91
              }
            ]
            """
        )
    )

    result = await tool.execute(
        WBSExtractionInput(document_text="Technical schedule includes transformer supply.")
    )

    assert result.success is True
    assert result.data[0].name == "Transformer supply"

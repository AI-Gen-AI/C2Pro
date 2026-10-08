"""Unmeasured risk extraction confidence must stay unknown."""

from src.analysis.adapters.ai.agents.risk_extractor import RiskExtractionCandidate, RiskImpact, RiskProbability
from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionTool
from src.analysis.domain.risk_categories import RiskCategory
from src.core.ai.tools import ToolResult, ToolStatus


def test_unscored_risk_remains_unassessed():
    candidate = RiskExtractionCandidate(
        title="Contract scope",
        category=RiskCategory.LEGAL,
        probability=RiskProbability.MEDIUM,
        impact=RiskImpact.HIGH,
    )
    assert candidate.confidence is None
    result = ToolResult(
        data=[candidate], status=ToolStatus.SUCCESS, success=True,
        model_used="test-model", input_tokens=0, output_tokens=0,
        cost_usd=0.0, latency_ms=0.0,
    )
    tool = RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())
    state = tool.inject_output_into_state({}, result)
    assert state["extracted_risks"][0]["confidence"] is None
    assert state["confidence_score"] is None

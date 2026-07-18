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

OBSERVED_FENCED_RESPONSE = """```json
{
  "risks": [
    {
      "category": "LEGAL",
      "title": "Ejecución por cuenta y riesgo del contratista sin reservas al Proyecto Constructivo",
      "summary": "El adjudicatario asume íntegramente el riesgo de la ejecución.",
      "description": "La Cláusula Segunda establece que el adjudicatario ejecuta por su cuenta y riesgo.",
      "probability": "MEDIUM",
      "impact": "HIGH",
      "source_quote": "por su cuenta y riesgo"
    }
  ]
}
```"""


def _tool() -> RiskExtractionTool:
    return RiskExtractionTool(anthropic_wrapper=object(), prompt_manager=object())


@pytest.mark.asyncio
async def test_risk_tool_logs_raw_output_length_and_parsed_count(monkeypatch) -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    events: list[tuple[str, dict[str, object]]] = []

    class Logger:
        def info(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    monkeypatch.setattr(risk_extraction_tool, "logger", Logger())

    tool = _tool()
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
                # stdlib logging carries structured fields via `extra=`; flat
                # structlog-style kwargs raise TypeError on a logging.Logger.
                "extra": {
                    "raw_output_chars": len(response.content),
                    "raw_output_sample": response.content,
                    "payload_type": "dict",
                    "payload_keys": ["risks"],
                    "candidate_item_count": 0,
                    "parsed_risk_count": 0,
                },
            },
        )
    ]


def test_extract_items_parses_observed_fenced_risks_shape() -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    payload = _tool()._extract_json_from_text(OBSERVED_FENCED_RESPONSE)

    items = _tool()._extract_items(payload)

    assert len(items) == 1
    assert items[0]["title"].startswith("Ejecución por cuenta y riesgo")


@pytest.mark.parametrize(
    "payload",
    [
        {"risks_identified": [{"title": "A"}]},
        {"identified_risks": [{"title": "A"}]},
        {"risk_items": [{"title": "A"}]},
        {"items": [{"title": "A"}]},
        {"findings": [{"title": "A"}]},
        {"data": {"risks": [{"title": "A"}]}},
        {"risk_1": {"title": "A"}, "risk_2": {"title": "B"}},
    ],
)
def test_extract_items_parses_common_payload_variants(payload: dict[str, object]) -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    items = _tool()._extract_items(payload)

    assert [item["title"] for item in items] in (["A"], ["A", "B"])


def test_extract_items_returns_empty_for_garbage_payload() -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    assert _tool()._extract_items({"message": "no risks found"}) == []


def test_coerce_risk_accepts_common_field_aliases() -> None:
    """Test Suite ID: TS-HOTFIX-ANALYSIS-HONEST-RISK-001."""
    risk = _tool()._coerce_risk(
        {
            "risk": "Garantía definitiva ejecutable",
            "detail": "La garantía puede ser ejecutada por incumplimiento.",
            "severity": "HIGH",
            "category": "FINANCIAL",
            "source": "garantía definitiva por importe de 4.713.657,54 €",
        }
    )

    assert risk is not None
    assert risk.title == "Garantía definitiva ejecutable"
    assert risk.impact.value == "HIGH"
    assert risk.source_quote == "garantía definitiva por importe de 4.713.657,54 €"

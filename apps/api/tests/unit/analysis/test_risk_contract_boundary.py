"""Issue #637 regression tests for the N4 canonical risk boundary."""

from src.analysis.adapters.graph.nodes import _risk_contract_item, _risk_contract_payload
from src.analysis.domain.contracts import Severity


def test_n4_boundary_preserves_critical_production_shape() -> None:
    """Legacy extractor output must cross N4 without CRITICAL -> HIGH coercion."""
    raw = {
        "category": "LEGAL",
        "title": "Uncapped liability",
        "summary": "Liability exposure requires immediate attention",
        "probability": "HIGH",
        "impact": "CRITICAL",
        "source_quote": (
            "The Contractor shall bear unlimited liability for all "
            "consequential losses."
        ),
        "risk_score": 12,
        "immediate_alert": True,
    }

    item = _risk_contract_item(raw)
    payload = _risk_contract_payload(raw)

    assert item.severity is Severity.CRITICAL
    assert item.impact is Severity.CRITICAL
    assert item.likelihood is Severity.HIGH
    assert payload["severity"] is Severity.CRITICAL
    assert payload["impact"] is Severity.CRITICAL

"""
Unit tests for the risk→signal bridge (v1 interim patch).

Refers to Suite ID: TS-UA-ANA-GRAPH-001.

Validates that N4 LLM-extracted risk dicts are correctly converted into
coherence FindingSignals with proper category mapping, impact scoring,
and coverage seeding. No DB required — pure data transformation.
"""
from __future__ import annotations

import pytest

from src.analysis.adapters.graph.risk_signal_bridge import (
    _IMPACT_TO_SCORE,
    RiskBridgeResult,
    build_risk_signals,
)
from src.coherence.models import FindingSignal

# ---------------------------------------------------------------------------
# Synthetic risk dict builders
# ---------------------------------------------------------------------------


def _risk(**overrides: object) -> dict:
    base: dict = {
        "category": "LEGAL",
        "title": "Cross-contract default risk",
        "summary": "Owner may default on cross-contract obligations",
        "risk_score": 8,
        "impact": "HIGH",
        "probability": 0.4,
        "source_quote": "The Contractor shall be entitled to suspend...",
        "immediate_alert": False,
        "mitigation_suggestion": "Include cross-default clause",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRiskToSignalMapping:
    """Core conversion: risk dict → FindingSignal."""

    def test_single_legal_risk(self):
        result = build_risk_signals([_risk()], clause_id="test-clause-1")
        assert len(result.signals) == 1
        sig = result.signals[0]
        assert isinstance(sig, FindingSignal)
        assert sig.rule_id == "EXTRACTOR-RISK"
        assert sig.clause_id == "test-clause-1"
        assert sig.source == "llm"
        assert sig.category == "LEGAL"
        assert sig.impact_score == pytest.approx(0.8)  # 8/10
        assert sig.confidence == 0.7
        assert sig.severity == "high"
        assert "Cross-contract" in sig.evidence_summary
        assert sig.quote == "The Contractor shall be entitled to suspend..."
        assert sig.raw_data["risk_score"] == 8
        assert result.coverage_seed == {"LEGAL": True}
        assert result.dropped_count == 0

    def test_empty_input(self):
        result = build_risk_signals([], clause_id="x")
        assert len(result.signals) == 0
        assert result.coverage_seed == {}
        assert result.dropped_count == 0

    def test_missing_category_dropped_not_fabricated(self):
        result = build_risk_signals([{"title": "No category", "summary": "x", "risk_score": 5}], clause_id="c1")
        assert len(result.signals) == 0
        assert result.coverage_seed == {}
        assert result.dropped_count == 1
        assert result.dropped_reasons == {"unknown_category": 1}

    def test_not_a_dict_dropped(self):
        result = build_risk_signals(["not_a_dict", 42], clause_id="c1")
        assert len(result.signals) == 0
        assert result.coverage_seed == {}
        assert result.dropped_count == 2
        assert result.dropped_reasons == {"not_a_dict": 2}

    def test_no_impact_signal_dropped(self):
        result = build_risk_signals(
            [{"category": "TECHNICAL", "title": "test", "summary": "x"}],
            clause_id="c1",
        )
        assert len(result.signals) == 0
        assert result.dropped_count == 1
        assert result.dropped_reasons == {"no_impact_signal": 1}


class TestImpactScoring:
    """risk_score (0-10) and impact-to-score mapping."""

    def test_risk_score_0_to_10_scale(self):
        result = build_risk_signals([_risk(risk_score=10)], clause_id="c")
        assert result.signals[0].impact_score == pytest.approx(1.0)

    def test_risk_score_0(self):
        result = build_risk_signals([_risk(risk_score=0)], clause_id="c")
        assert result.signals[0].impact_score == pytest.approx(0.0)

    def test_risk_score_100_scale_legacy(self):
        """Legacy extractor may return 0-100. Bridge normalizes div by 100."""
        result = build_risk_signals([_risk(risk_score=85)], clause_id="c")
        # 85 <= 10? No. So 85/100 = 0.85
        assert result.signals[0].impact_score == pytest.approx(0.85)

    def test_risk_score_negative_ignored_fallback_to_impact(self):
        result = build_risk_signals([_risk(risk_score=-5, impact="MEDIUM")], clause_id="c")
        # -5 is not >= 0, so falls back to impact MEDIUM = 0.5
        assert result.signals[0].impact_score == pytest.approx(0.5)

    def test_impact_score_mapping(self):
        for label, expected in _IMPACT_TO_SCORE.items():
            result = build_risk_signals([_risk(risk_score=None, impact=label)], clause_id="c")
            assert result.signals[0].impact_score == pytest.approx(expected), f"{label}→{expected}"


class TestCategoryMapping:
    """Legacy category names map to canonical CoherenceCategory."""

    def test_financial_maps_to_budget(self):
        result = build_risk_signals([_risk(category="FINANCIAL", risk_score=5)], clause_id="c")
        assert result.signals[0].category == "BUDGET"
        assert result.coverage_seed == {"BUDGET": True}

    def test_schedule_maps_to_time(self):
        result = build_risk_signals([_risk(category="SCHEDULE", risk_score=5)], clause_id="c")
        assert result.signals[0].category == "TIME"
        assert result.coverage_seed == {"TIME": True}

    def test_unknown_category_dropped(self):
        result = build_risk_signals([{"category": "COSMIC_RAY", "title": "x", "risk_score": 5}], clause_id="c")
        assert len(result.signals) == 0
        assert result.dropped_reasons == {"unknown_category": 1}


class TestSeverityMapping:
    """Impact label maps to SeverityLevel."""

    def test_critical_impact(self):
        result = build_risk_signals([_risk(impact="CRITICAL")], clause_id="c")
        assert result.signals[0].severity == "critical"

    def test_low_impact(self):
        result = build_risk_signals([_risk(impact="LOW")], clause_id="c")
        assert result.signals[0].severity == "low"

    def test_unknown_impact_defaults_to_medium(self):
        result = build_risk_signals([_risk(impact="UNKNOWN_BUCKET")], clause_id="c")
        assert result.signals[0].severity == "medium"


class TestCoverageSeeding:
    """Coverage seed marks assessed_findings for each category with a risk."""

    def test_multi_category_coverage(self):
        risks = [
            _risk(category="LEGAL", risk_score=5),
            _risk(category="TECHNICAL", risk_score=6),
            _risk(category="LEGAL", risk_score=7),  # duplicate category
            _risk(category="QUALITY", risk_score=4),
        ]
        result = build_risk_signals(risks, clause_id="c")
        assert len(result.signals) == 4
        assert result.coverage_seed == {"LEGAL": True, "TECHNICAL": True, "QUALITY": True}

    def test_coverage_seed_is_bool(self):
        result = build_risk_signals([_risk()], clause_id="c")
        assert result.coverage_seed["LEGAL"] is True


class TestRiskBridgeResult:
    """RiskBridgeResult dataclass integrity."""

    def test_frozen_immutability(self):
        r = RiskBridgeResult(signals=(), coverage_seed={}, dropped_count=0, dropped_reasons={})
        with pytest.raises(Exception):
            r.dropped_count = 5  # type: ignore[misc]

    def test_signals_are_tuple(self):
        risks = [_risk(), _risk(category="TECHNICAL", risk_score=4)]
        result = build_risk_signals(risks, clause_id="c")
        assert isinstance(result.signals, tuple)
        assert len(result.signals) == 2

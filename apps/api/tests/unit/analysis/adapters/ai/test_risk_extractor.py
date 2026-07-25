"""
TS-UD-ANL-RSK-001: Unit tests for risk extraction helper functions.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.analysis.adapters.ai.agents.risk_extractor import (
    RiskExtractorAgent,
    RiskImpact,
    RiskItem,
    RiskProbability,
    _clean_text,
    _coerce_risk,
    _extract_items,
    _filter_relevant_text,
    _is_immediate_alert,
    _normalize_category,
    _normalize_impact,
    _normalize_probability,
    _risk_score,
    _split_paragraphs,
    _truncate,
)
from src.analysis.domain.risk_categories import RiskCategory


class TestCleanText:
    def test_strips_whitespace(self) -> None:
        assert _clean_text("  hello  ") == "hello"

    def test_empty_string_returns_none(self) -> None:
        assert _clean_text("   ") is None

    def test_non_string_returns_none(self) -> None:
        assert _clean_text(123) is None
        assert _clean_text(None) is None


class TestNormalizeCategory:
    def test_canonical_category(self) -> None:
        assert _normalize_category("SCOPE") == RiskCategory.SCOPE

    def test_alias_category(self) -> None:
        assert _normalize_category("FINANCIAL") == RiskCategory.BUDGET
        assert _normalize_category("TIME") == RiskCategory.SCHEDULE

    def test_unknown_category_returns_none(self) -> None:
        assert _normalize_category("NONSENSE") is None

    def test_none_returns_none(self) -> None:
        assert _normalize_category(None) is None

    def test_non_string_returns_none(self) -> None:
        assert _normalize_category(42) is None


class TestNormalizeProbability:
    def test_valid_values(self) -> None:
        assert _normalize_probability("LOW") == RiskProbability.LOW
        assert _normalize_probability("medium") == RiskProbability.MEDIUM
        assert _normalize_probability("HIGH") == RiskProbability.HIGH

    def test_invalid_returns_none(self) -> None:
        assert _normalize_probability("EXTREME") is None
        assert _normalize_probability(None) is None
        assert _normalize_probability(5) is None


class TestNormalizeImpact:
    def test_valid_values(self) -> None:
        assert _normalize_impact("LOW") == RiskImpact.LOW
        assert _normalize_impact("CRITICAL") == RiskImpact.CRITICAL
        assert _normalize_impact("medium") == RiskImpact.MEDIUM

    def test_invalid_returns_none(self) -> None:
        assert _normalize_impact("SEVERE") is None


class TestIsImmediateAlert:
    def test_alert_when_critical_high(self) -> None:
        risk = RiskItem(
            category=RiskCategory.LEGAL,
            probability=RiskProbability.HIGH,
            impact=RiskImpact.CRITICAL,
        )
        assert _is_immediate_alert(risk) is True

    def test_not_alert_when_low_high(self) -> None:
        risk = RiskItem(
            category=RiskCategory.SCOPE,
            probability=RiskProbability.HIGH,
            impact=RiskImpact.LOW,
        )
        assert _is_immediate_alert(risk) is False

    def test_not_alert_when_critical_low(self) -> None:
        risk = RiskItem(
            category=RiskCategory.BUDGET,
            probability=RiskProbability.LOW,
            impact=RiskImpact.CRITICAL,
        )
        assert _is_immediate_alert(risk) is False


class TestRiskScore:
    def test_critical_high_is_12(self) -> None:
        risk = RiskItem(category=RiskCategory.LEGAL, probability=RiskProbability.HIGH, impact=RiskImpact.CRITICAL)
        assert _risk_score(risk) == 12

    def test_medium_medium_is_4(self) -> None:
        risk = RiskItem(category=RiskCategory.SCHEDULE, probability=RiskProbability.MEDIUM, impact=RiskImpact.MEDIUM)
        assert _risk_score(risk) == 4

    def test_low_low_is_1(self) -> None:
        risk = RiskItem(category=RiskCategory.QUALITY, probability=RiskProbability.LOW, impact=RiskImpact.LOW)
        assert _risk_score(risk) == 1


class TestExtractItems:
    def test_extracts_from_dict_with_risks_list(self) -> None:
        payload = {"risks": [{"title": "Risk A"}, {"title": "Risk B"}]}
        result = _extract_items(payload)
        assert len(result) == 2

    def test_extracts_single_dict(self) -> None:
        payload = {"risks": {"title": "Only risk"}}
        result = _extract_items(payload)
        assert len(result) == 1

    def test_empty_payload_returns_empty(self) -> None:
        assert _extract_items({"risks": []}) == []
        assert _extract_items({}) == []

    def test_payload_list_at_root(self) -> None:
        result = _extract_items([{"title": "A"}, "not_dict"])
        assert len(result) == 1

    def test_non_dict_non_list_returns_empty(self) -> None:
        assert _extract_items("string") == []
        assert _extract_items(None) == []


class TestCoerceRisk:
    def test_full_valid_risk(self) -> None:
        item = {
            "title": "Multa excesiva",
            "summary": "Riesgo de penalizacion",
            "description": "La clausula impone multas diarias sin tope",
            "category": "LEGAL",
            "probability": "HIGH",
            "impact": "CRITICAL",
            "mitigation_suggestion": "Negociar tope",
            "source_quote": "multa diaria de $5000",
        }
        risk = _coerce_risk(item)
        assert risk is not None
        assert risk.title == "Multa excesiva"
        assert risk.category == RiskCategory.LEGAL
        assert risk.probability == RiskProbability.HIGH
        assert risk.impact == RiskImpact.CRITICAL

    def test_missing_fields_returns_none(self) -> None:
        assert _coerce_risk({"title": "Only title"}) is None
        assert _coerce_risk({"category": "LEGAL"}) is None

    def test_empty_text_fields_return_none(self) -> None:
        risk = _coerce_risk({"title": "", "summary": "", "description": "", "category": "SCOPE", "probability": "LOW", "impact": "LOW"})
        assert risk is None

    def test_invalid_category_returns_none(self) -> None:
        risk = _coerce_risk({"title": "X", "category": "INVALID", "probability": "LOW", "impact": "LOW"})
        assert risk is None


class TestSplitParagraphs:
    def test_splits_on_double_newline(self) -> None:
        text = "P1\n\nP2\n\nP3"
        result = _split_paragraphs(text)
        assert result == ["P1", "P2", "P3"]

    def test_single_paragraph(self) -> None:
        assert _split_paragraphs("Single paragraph") == ["Single paragraph"]

    def test_empty_string(self) -> None:
        assert _split_paragraphs("") == []


class TestFilterRelevantText:
    def test_includes_relevant_content(self) -> None:
        text = "condiciones particulares del proyecto\n\nseccion irrelevante de precios"
        result = _filter_relevant_text(text)
        assert "condiciones particulares" in result

    def test_excludes_price_table(self) -> None:
        text = "tabla de precios unitarios\n\ncondiciones especiales del contrato"
        result = _filter_relevant_text(text)
        assert "tabla de precios" not in result
        assert "condiciones especiales" in result

    def test_no_relevant_returns_all(self) -> None:
        text = "texto generico sin palabras clave"
        result = _filter_relevant_text(text)
        assert "texto generico" in result


class TestTruncate:
    def test_short_text_passes_through(self) -> None:
        assert _truncate("short", max_chars=100) == "short"

    def test_long_text_truncated(self) -> None:
        result = _truncate("x" * 200, max_chars=100)
        assert len(result) <= 100


class TestRiskExtractorAgent:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self) -> None:
        agent = RiskExtractorAgent()
        result = await agent.extract("")
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty(self) -> None:
        agent = RiskExtractorAgent()
        result = await agent.extract("   \n  ")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_with_mocked_llm(self) -> None:
        llm_payload = {
            "risks": [
                {
                    "title": "Multa excesiva",
                    "summary": "Penalizacion diaria sin tope",
                    "description": "La clausula 10 impone multas",
                    "category": "LEGAL",
                    "probability": "HIGH",
                    "impact": "CRITICAL",
                }
            ]
        }

        with patch.object(RiskExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = RiskExtractorAgent()
            result = await agent.extract("Texto del contrato relevante")
            assert len(result) == 1
            assert result[0].title == "Multa excesiva"
            assert result[0].risk_score == 12
            assert result[0].immediate_alert is True

    @pytest.mark.asyncio
    async def test_extract_sorts_by_score_descending(self) -> None:
        llm_payload = {
            "risks": [
                {"title": "Low risk", "category": "SCOPE", "probability": "LOW", "impact": "LOW"},
                {"title": "High risk", "category": "LEGAL", "probability": "HIGH", "impact": "CRITICAL"},
            ]
        }

        with patch.object(RiskExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = RiskExtractorAgent()
            result = await agent.extract("text")
            assert result[0].title == "High risk"
            assert result[1].title == "Low risk"

    @pytest.mark.asyncio
    async def test_extract_skips_invalid_items(self) -> None:
        llm_payload = {
            "risks": [
                {"title": "Valid", "category": "LEGAL", "probability": "HIGH", "impact": "HIGH"},
                {"title": "No category", "probability": "LOW", "impact": "LOW"},
            ]
        }

        with patch.object(RiskExtractorAgent, "_run_with_retry", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_payload
            agent = RiskExtractorAgent()
            result = await agent.extract("text")
            assert len(result) == 1

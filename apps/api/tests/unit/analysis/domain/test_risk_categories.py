"""Tests for the canonical six-value risk-category taxonomy.

Locks the taxonomy end-to-end: enum membership, alias normalization, and
the deterministic mock-mode extractor must all speak the same six names.
"""

from __future__ import annotations

import pytest

from src.analysis.domain.ai_extraction import DeterministicRiskRulesService
from src.analysis.domain.risk_categories import (
    CANONICAL_CATEGORIES,
    RiskCategory,
    normalize_category,
)

CANONICAL_SET = {"LEGAL", "SCHEDULE", "QUALITY", "SCOPE", "TECHNICAL", "BUDGET"}


class TestRiskCategoryEnum:
    def test_enum_has_exactly_six_canonical_values(self) -> None:
        assert {cat.value for cat in RiskCategory} == CANONICAL_SET

    def test_canonical_frozenset_matches_enum(self) -> None:
        assert CANONICAL_CATEGORIES == CANONICAL_SET


class TestNormalizeCategory:
    @pytest.mark.parametrize("raw", sorted(CANONICAL_SET))
    def test_canonical_values_pass_through(self, raw: str) -> None:
        assert normalize_category(raw) is RiskCategory(raw)

    @pytest.mark.parametrize("raw", ["legal", "Legal", "  LEGAL  ", "lEgAl"])
    def test_case_and_whitespace_normalized(self, raw: str) -> None:
        assert normalize_category(raw) is RiskCategory.LEGAL

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("FINANCIAL", RiskCategory.BUDGET),
            ("financial", RiskCategory.BUDGET),
            ("COST", RiskCategory.BUDGET),
            ("Presupuesto", RiskCategory.BUDGET),
            ("TIME", RiskCategory.SCHEDULE),
            ("timing", RiskCategory.SCHEDULE),
            ("Cronograma", RiskCategory.SCHEDULE),
            ("HSE", RiskCategory.QUALITY),
            ("safety", RiskCategory.QUALITY),
            ("Environmental", RiskCategory.QUALITY),
            ("Calidad", RiskCategory.QUALITY),
            ("Alcance", RiskCategory.SCOPE),
            ("Tecnico", RiskCategory.TECHNICAL),
        ],
    )
    def test_legacy_aliases_resolve_to_canonical(
        self, raw: str, expected: RiskCategory
    ) -> None:
        assert normalize_category(raw) is expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "WEATHER", "unknown-thing", 42])
    def test_unknown_returns_none(self, raw) -> None:
        assert normalize_category(raw) is None


class TestDeterministicRiskRulesCoverAllSix:
    """The mock-mode extractor must cover every canonical category."""

    def test_all_six_categories_emitted_from_rich_text(self) -> None:
        text = (
            "This contract imposes a penalty 2% per delay. "
            "Payment within 30 days against certified milestones. "
            "Warranty period is 24 months. "
            "Completion deadline is December. "
            "Scope as required by the contractor. "
            "Specification and compliance standards referenced."
        )

        risks = DeterministicRiskRulesService().extract(text)
        categories = {r["category"] for r in risks}

        assert CANONICAL_SET.issubset(categories), (
            f"Missing canonical categories: {CANONICAL_SET - categories}"
        )

    def test_no_legacy_category_names_emitted(self) -> None:
        text = (
            "penalty for delay; payment within 30 days; warranty; deadline; "
            "scope; specification"
        )
        risks = DeterministicRiskRulesService().extract(text)
        emitted = {r["category"] for r in risks}
        legacy = {"FINANCIAL", "TIME", "HSE"}
        assert not (emitted & legacy), (
            f"Deterministic rules must not emit legacy category names: {emitted & legacy}"
        )

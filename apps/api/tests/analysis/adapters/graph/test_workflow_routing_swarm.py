"""
QA Swarm — Auto-generated tests for src/analysis/adapters/graph/nodes.py

Covers the pure routing and utility functions that have zero unit test coverage:
- _next_after_critique: all 5 routing branches (human_interrupt, risk_extractor,
  budget_parser, wbs_extractor, save_to_db)
- _average_confidence: empty list, items without confidence, averaged values
- DOC_TYPES tuple membership

These are pure functions with no I/O, making them ideal for fast, deterministic unit tests.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.adapters.graph.nodes import (
    DOC_TYPES,
    _average_confidence,
    _next_after_critique,
)


# ---------------------------------------------------------------------------
# State helper
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal ProjectState-compatible dict for testing routing logic."""
    defaults: dict[str, Any] = {
        "project_id": "proj-001",
        "document_id": "doc-001",
        "tenant_id": None,
        "document_text": "Sample contract text",
        "anonymized_text": "",
        "doc_type": "contract",
        "extracted_risks": [],
        "extracted_wbs": [],
        "extracted_budget": [],
        "confidence_score": 0.9,
        "critique_notes": "",
        "retry_count": 0,
        "human_approval_required": False,
        "human_feedback": "",
        "analysis_id": None,
        "messages": [],
        "error": None,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# TestNextAfterCritique
# ---------------------------------------------------------------------------


class TestNextAfterCritique:
    """Tests for _next_after_critique routing function."""

    @pytest.mark.unit
    def test_human_approval_required_routes_to_human_interrupt(self) -> None:
        state = _make_state(human_approval_required=True)
        assert _next_after_critique(state) == "human_interrupt"

    @pytest.mark.unit
    def test_human_approval_takes_priority_over_critique_notes(self) -> None:
        state = _make_state(
            human_approval_required=True,
            critique_notes="Some notes",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "human_interrupt"

    @pytest.mark.unit
    def test_contract_doc_type_with_critique_routes_to_risk_extractor(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="Missing clause details",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "risk_extractor"

    @pytest.mark.unit
    def test_budget_doc_type_with_critique_routes_to_budget_parser(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="Budget items incomplete",
            retry_count=1,
            doc_type="budget",
        )
        assert _next_after_critique(state) == "budget_parser"

    @pytest.mark.unit
    def test_technical_spec_doc_type_with_critique_routes_to_wbs_extractor(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="WBS items missing",
            retry_count=1,
            doc_type="technical_spec",
        )
        assert _next_after_critique(state) == "wbs_extractor"

    @pytest.mark.unit
    def test_unknown_doc_type_with_critique_routes_to_wbs_extractor(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="Some critique",
            retry_count=1,
            doc_type="other",
        )
        assert _next_after_critique(state) == "wbs_extractor"

    @pytest.mark.unit
    def test_no_critique_notes_routes_to_save_to_db(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "save_to_db"

    @pytest.mark.unit
    def test_retry_count_zero_routes_to_save_to_db(self) -> None:
        """retry_count=0 means `retry_count > 0` is False → falls through to save_to_db."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="Has notes",
            retry_count=0,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "save_to_db"

    @pytest.mark.unit
    def test_retry_count_at_max_two_still_retries(self) -> None:
        """retry_count=2 satisfies `retry_count > 0` AND `retry_count <= 2` → retries."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="Still has issues",
            retry_count=2,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "risk_extractor"

    @pytest.mark.unit
    def test_retry_count_exceeds_max_routes_to_save_to_db(self) -> None:
        """retry_count=3 fails the `retry_count <= 2` guard → routes to save_to_db."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="Too many retries",
            retry_count=3,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "save_to_db"

    @pytest.mark.unit
    def test_no_human_approval_no_critique_routes_to_save_to_db(self) -> None:
        state = _make_state(
            human_approval_required=False,
            critique_notes="",
            retry_count=0,
        )
        assert _next_after_critique(state) == "save_to_db"


# ---------------------------------------------------------------------------
# TestAverageConfidence
# ---------------------------------------------------------------------------


class TestAverageConfidence:
    """Tests for _average_confidence utility function."""

    @pytest.mark.unit
    def test_empty_list_returns_zero(self) -> None:
        assert _average_confidence([]) == 0.0

    @pytest.mark.unit
    def test_items_without_confidence_key_returns_fallback(self) -> None:
        """When items exist but none have valid confidence → returns 0.9 fallback."""
        items = [{"title": "Risk A"}, {"title": "Risk B"}]
        assert _average_confidence(items) == 0.9

    @pytest.mark.unit
    def test_items_with_none_confidence_returns_fallback(self) -> None:
        items = [{"confidence": None}, {"confidence": None}]
        assert _average_confidence(items) == 0.9

    @pytest.mark.unit
    def test_single_item_returns_its_confidence(self) -> None:
        items = [{"confidence": 0.75}]
        assert pytest.approx(_average_confidence(items)) == 0.75

    @pytest.mark.unit
    def test_multiple_items_returns_mean(self) -> None:
        items = [{"confidence": 0.8}, {"confidence": 0.6}, {"confidence": 1.0}]
        expected = (0.8 + 0.6 + 1.0) / 3
        assert pytest.approx(_average_confidence(items)) == expected

    @pytest.mark.unit
    def test_integer_confidence_values_accepted(self) -> None:
        items = [{"confidence": 1}, {"confidence": 0}]
        assert pytest.approx(_average_confidence(items)) == 0.5

    @pytest.mark.unit
    def test_mixed_valid_and_invalid_confidence(self) -> None:
        """Only valid numeric confidences are averaged; None entries are skipped."""
        items = [{"confidence": 0.9}, {"confidence": None}, {"confidence": 0.7}]
        expected = (0.9 + 0.7) / 2
        assert pytest.approx(_average_confidence(items)) == expected


# ---------------------------------------------------------------------------
# TestDocTypes
# ---------------------------------------------------------------------------


class TestDocTypes:
    """Tests for the DOC_TYPES constant used in routing decisions."""

    @pytest.mark.unit
    def test_contract_in_doc_types(self) -> None:
        assert "contract" in DOC_TYPES

    @pytest.mark.unit
    def test_budget_in_doc_types(self) -> None:
        assert "budget" in DOC_TYPES

    @pytest.mark.unit
    def test_technical_spec_in_doc_types(self) -> None:
        assert "technical_spec" in DOC_TYPES

    @pytest.mark.unit
    def test_unknown_not_in_doc_types(self) -> None:
        assert "unknown" not in DOC_TYPES

    @pytest.mark.unit
    def test_doc_types_is_tuple(self) -> None:
        assert isinstance(DOC_TYPES, tuple)

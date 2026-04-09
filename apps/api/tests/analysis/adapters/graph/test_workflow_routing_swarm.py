"""
C2Pro - Workflow Routing Unit Tests (Swarm)

Tests for pure routing and confidence functions in
src/analysis/adapters/graph/nodes.py.

Coverage:
- _next_after_critique: all routing branches
    human_approval_required → human_interrupt
    critique_notes + retry_count in (1,2] + doc_type contract → risk_extractor
    critique_notes + retry_count in (1,2] + doc_type budget → budget_parser
    critique_notes + retry_count in (1,2] + other doc_type → wbs_extractor
    no critique_notes → save_to_db
    retry_count == 0 → save_to_db
    retry_count > 2 → save_to_db

- _average_confidence:
    empty items list → 0.0
    items exist but no valid confidence values → 0.9
    items with numeric confidence values → arithmetic mean

- DOC_TYPES constant: expected members present
"""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.adapters.graph.workflow import _next_after_critique_v2 as _next_after_critique
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.analysis.domain.prompts import DOC_TYPES

# Use domain service for confidence calculation (replaces removed _average_confidence)
_critique_evaluator = CritiqueEvaluationService()
_average_confidence = _critique_evaluator.calculate_confidence

# ---------------------------------------------------------------------------
# State factory
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid ProjectState dict for testing."""
    defaults: dict[str, Any] = {
        "project_id": "proj-001",
        "document_id": "doc-001",
        "tenant_id": None,
        "document_text": "Sample document text",
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


# ===========================================================================
# TestNextAfterCritique
# ===========================================================================


class TestNextAfterCritique:
    """Unit tests for the _next_after_critique routing function."""

    @pytest.mark.red_phase
    def test_human_approval_required_true_returns_human_interrupt(self) -> None:
        """When human_approval_required is True, route to human_interrupt regardless of other fields."""
        state = _make_state(
            human_approval_required=True,
            critique_notes="some notes",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "human_interrupt"

    @pytest.mark.red_phase
    def test_human_approval_required_overrides_contract_retry(self) -> None:
        """human_approval_required=True takes precedence over contract retry path."""
        state = _make_state(
            human_approval_required=True,
            critique_notes="critical issue",
            retry_count=2,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "human_interrupt"

    @pytest.mark.red_phase
    def test_contract_with_notes_and_retry_count_1_returns_risk_extractor(self) -> None:
        """doc_type='contract', critique_notes set, retry_count=1 → risk_extractor."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="missing clause",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "risk_extractor"

    @pytest.mark.red_phase
    def test_contract_with_notes_and_retry_count_2_returns_risk_extractor(self) -> None:
        """doc_type='contract', critique_notes set, retry_count=2 (boundary) → risk_extractor."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="incomplete extraction",
            retry_count=2,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "risk_extractor"

    @pytest.mark.red_phase
    def test_budget_with_notes_and_retry_count_1_returns_budget_parser(self) -> None:
        """doc_type='budget', critique_notes set, retry_count=1 → budget_parser."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="budget line items missing",
            retry_count=1,
            doc_type="budget",
        )
        assert _next_after_critique(state) == "budget_parser"

    @pytest.mark.red_phase
    def test_budget_with_notes_and_retry_count_2_returns_budget_parser(self) -> None:
        """doc_type='budget', critique_notes set, retry_count=2 → budget_parser."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="cost columns absent",
            retry_count=2,
            doc_type="budget",
        )
        assert _next_after_critique(state) == "budget_parser"

    @pytest.mark.red_phase
    def test_technical_spec_with_notes_and_retry_count_1_returns_wbs_extractor(self) -> None:
        """doc_type='technical_spec', critique_notes set, retry_count=1 → wbs_extractor."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="WBS entries incomplete",
            retry_count=1,
            doc_type="technical_spec",
        )
        assert _next_after_critique(state) == "wbs_extractor"

    @pytest.mark.red_phase
    def test_unknown_doc_type_with_notes_and_retry_count_1_returns_wbs_extractor(self) -> None:
        """Unrecognised doc_type falls through to wbs_extractor when notes and retry active."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="parse issue",
            retry_count=1,
            doc_type="other_type",
        )
        assert _next_after_critique(state) == "wbs_extractor"

    @pytest.mark.red_phase
    def test_empty_critique_notes_returns_save_to_db(self) -> None:
        """Empty critique_notes always routes to save_to_db even with retry_count > 0."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="",
            retry_count=1,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "stakeholder_extractor"

    @pytest.mark.red_phase
    def test_retry_count_zero_with_notes_returns_save_to_db(self) -> None:
        """retry_count=0 routes to save_to_db even when critique_notes is non-empty."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="some critique note",
            retry_count=0,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "stakeholder_extractor"

    @pytest.mark.red_phase
    def test_retry_count_3_returns_save_to_db(self) -> None:
        """retry_count=3 (> 2) routes to save_to_db even with notes and a recognised doc_type."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="persistent issues",
            retry_count=3,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "stakeholder_extractor"

    @pytest.mark.red_phase
    def test_retry_count_large_returns_save_to_db(self) -> None:
        """Any retry_count beyond 2 routes to save_to_db."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="persistent issues",
            retry_count=100,
            doc_type="budget",
        )
        assert _next_after_critique(state) == "stakeholder_extractor"

    @pytest.mark.red_phase
    def test_no_notes_no_retry_returns_save_to_db(self) -> None:
        """Baseline state with no notes and retry_count=0 goes directly to save_to_db."""
        state = _make_state(
            human_approval_required=False,
            critique_notes="",
            retry_count=0,
            doc_type="contract",
        )
        assert _next_after_critique(state) == "stakeholder_extractor"


# ===========================================================================
# TestAverageConfidence
# ===========================================================================


class TestAverageConfidence:
    """Unit tests for the _average_confidence helper function."""

    @pytest.mark.red_phase
    def test_empty_items_list_returns_0_0(self) -> None:
        """Empty items list → 0.0 (no items, no confidences)."""
        assert _average_confidence([]) == pytest.approx(0.0)

    @pytest.mark.red_phase
    def test_items_with_no_confidence_key_returns_0_9(self) -> None:
        """Items present but none have a 'confidence' key → fallback 0.9."""
        items = [{"title": "Risk A"}, {"title": "Risk B"}]
        assert _average_confidence(items) == pytest.approx(0.9)

    @pytest.mark.red_phase
    def test_items_with_none_confidence_returns_0_9(self) -> None:
        """Items with None as confidence value → not a numeric type → fallback 0.9."""
        items = [{"confidence": None}, {"confidence": None}]
        assert _average_confidence(items) == pytest.approx(0.9)

    @pytest.mark.red_phase
    def test_items_with_string_confidence_returns_0_9(self) -> None:
        """Items with non-numeric string confidence values → fallback 0.9."""
        items = [{"confidence": "high"}, {"confidence": "medium"}]
        assert _average_confidence(items) == pytest.approx(0.9)

    @pytest.mark.red_phase
    def test_single_item_with_confidence_returns_that_value(self) -> None:
        """Single item with a numeric confidence → returns that confidence value."""
        items = [{"confidence": 0.75}]
        assert _average_confidence(items) == pytest.approx(0.75)

    @pytest.mark.red_phase
    def test_two_items_returns_arithmetic_mean(self) -> None:
        """Two items with confidence values → returns their arithmetic mean."""
        items = [{"confidence": 0.8}, {"confidence": 0.6}]
        assert _average_confidence(items) == pytest.approx(0.7)

    @pytest.mark.red_phase
    def test_three_items_returns_arithmetic_mean(self) -> None:
        """Three items → arithmetic mean of all confidence values."""
        items = [{"confidence": 0.9}, {"confidence": 0.7}, {"confidence": 0.5}]
        expected = (0.9 + 0.7 + 0.5) / 3
        assert _average_confidence(items) == pytest.approx(expected)

    @pytest.mark.red_phase
    def test_integer_confidence_values_are_accepted(self) -> None:
        """Integer confidence values (isinstance int) are included in the average."""
        items = [{"confidence": 1}, {"confidence": 0}]
        assert _average_confidence(items) == pytest.approx(0.5)

    @pytest.mark.red_phase
    def test_mixed_valid_and_invalid_confidence_uses_only_valid(self) -> None:
        """Only numeric confidence entries contribute to the mean; others are ignored."""
        items = [
            {"confidence": 0.8},
            {"confidence": "bad"},
            {"confidence": 0.6},
            {"title": "no conf key"},
        ]
        # Only 0.8 and 0.6 are valid numeric confidences
        expected = (0.8 + 0.6) / 2
        assert _average_confidence(items) == pytest.approx(expected)

    @pytest.mark.red_phase
    def test_all_confidence_values_at_zero_returns_zero(self) -> None:
        """Items all with confidence 0.0 → mean is 0.0."""
        items = [{"confidence": 0.0}, {"confidence": 0.0}]
        assert _average_confidence(items) == pytest.approx(0.0)

    @pytest.mark.red_phase
    def test_all_confidence_values_at_one_returns_one(self) -> None:
        """Items all with confidence 1.0 → mean is 1.0."""
        items = [{"confidence": 1.0}, {"confidence": 1.0}, {"confidence": 1.0}]
        assert _average_confidence(items) == pytest.approx(1.0)


# ===========================================================================
# TestDocTypes
# ===========================================================================


class TestDocTypes:
    """Unit tests verifying the DOC_TYPES constant."""

    @pytest.mark.red_phase
    def test_doc_types_contains_contract(self) -> None:
        """DOC_TYPES includes 'contract'."""
        assert "contract" in DOC_TYPES

    @pytest.mark.red_phase
    def test_doc_types_contains_technical_spec(self) -> None:
        """DOC_TYPES includes 'technical_spec'."""
        assert "technical_spec" in DOC_TYPES

    @pytest.mark.red_phase
    def test_doc_types_contains_budget(self) -> None:
        """DOC_TYPES includes 'budget'."""
        assert "budget" in DOC_TYPES

    @pytest.mark.red_phase
    def test_doc_types_has_expected_members(self) -> None:
        """DOC_TYPES has the four expected document type strings."""
        assert len(DOC_TYPES) == 4
        assert "schedule" in DOC_TYPES

    @pytest.mark.red_phase
    def test_doc_types_is_tuple(self) -> None:
        """DOC_TYPES is a tuple as declared in the source."""
        assert isinstance(DOC_TYPES, tuple)

    @pytest.mark.red_phase
    def test_doc_types_does_not_contain_unknown_string(self) -> None:
        """Arbitrary unknown strings are not present in DOC_TYPES."""
        assert "invoice" not in DOC_TYPES

    @pytest.mark.red_phase
    def test_doc_types_does_not_contain_report(self) -> None:
        """'report' is not a recognised document type."""
        assert "report" not in DOC_TYPES

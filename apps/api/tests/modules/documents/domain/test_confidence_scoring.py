"""
Confidence Scoring (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-CNF-001.
"""

from __future__ import annotations

import pytest

from src.documents.domain.services.entity_extraction import calculate_confidence_score


class TestConfidenceScoring:
    """Refers to Suite ID: TS-UD-DOC-CNF-001."""

    def test_clear_structure_results_in_high_confidence(self):
        score = calculate_confidence_score(
            text="1. Objeto. 2. Precio. 3. Plazo.",
            extracted_entities_count=6,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        assert score >= 0.9

    def test_ambiguous_document_results_in_low_confidence(self):
        score = calculate_confidence_score(
            text="...", extracted_entities_count=0, parsing_errors_count=2, ambiguous_markers_count=3
        )
        assert score <= 0.5

    def test_score_is_clamped_to_range_0_1(self):
        low = calculate_confidence_score(
            text="x",
            extracted_entities_count=0,
            parsing_errors_count=100,
            ambiguous_markers_count=100,
        )
        high = calculate_confidence_score(
            text="1. A 2. B 3. C",
            extracted_entities_count=200,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        assert 0.0 <= low <= 1.0
        assert 0.0 <= high <= 1.0

    def test_parsing_errors_reduce_confidence(self):
        baseline = calculate_confidence_score(
            text="1. Alcance 2. Precio",
            extracted_entities_count=4,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        with_errors = calculate_confidence_score(
            text="1. Alcance 2. Precio",
            extracted_entities_count=4,
            parsing_errors_count=2,
            ambiguous_markers_count=0,
        )
        assert with_errors < baseline

    def test_more_extracted_entities_increase_confidence(self):
        low_entities = calculate_confidence_score(
            text="Contrato base",
            extracted_entities_count=1,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        high_entities = calculate_confidence_score(
            text="Contrato base",
            extracted_entities_count=8,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        assert high_entities > low_entities

    def test_ambiguous_markers_reduce_confidence(self):
        no_ambiguity = calculate_confidence_score(
            text="Clausula clara",
            extracted_entities_count=3,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        with_ambiguity = calculate_confidence_score(
            text="Clausula clara",
            extracted_entities_count=3,
            parsing_errors_count=0,
            ambiguous_markers_count=2,
        )
        assert with_ambiguity < no_ambiguity

    @pytest.mark.parametrize(
        "text,expected_bonus",
        [
            ("1. Alcance 2. Presupuesto 3. Plazo", True),
            ("Texto libre sin numeracion", False),
        ],
    )
    def test_structured_text_bonus(self, text: str, expected_bonus: bool):
        structured = calculate_confidence_score(
            text=text,
            extracted_entities_count=3,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        unstructured = calculate_confidence_score(
            text="texto libre sin marcas",
            extracted_entities_count=3,
            parsing_errors_count=0,
            ambiguous_markers_count=0,
        )
        if expected_bonus:
            assert structured > unstructured
        else:
            assert structured <= 1.0

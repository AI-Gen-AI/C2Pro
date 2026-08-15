"""Tests for the 'technical specs referenced but not provided' hint.

When the technical dimension is withheld for lack of evidence but the documents
reference a separate technical pliego, /evaluate appends an actionable hint to
score_reason — honest (never invents a score) and actionable (says what to upload).
"""

from __future__ import annotations

from src.coherence.models import Clause, EnrichedCoherenceResult
from src.coherence.router import (
    _annotate_missing_technical_hint,
    _technical_specs_referenced,
)


def _clause(text: str) -> Clause:
    return Clause(id="c-1", text=text, data={})


def test_technical_specs_referenced_detects_pliego() -> None:
    assert _technical_specs_referenced(
        [_clause("El adjudicatario ejecutará conforme al Pliego de prescripciones técnicas.")]
    )
    assert not _technical_specs_referenced([_clause("El precio del contrato es 100 euros.")])


def test_hint_added_when_technical_missing_and_referenced() -> None:
    result = EnrichedCoherenceResult(
        overall_score=80.0, score_missing_dimensions=["TECHNICAL"], score_reason=None
    )
    _annotate_missing_technical_hint(
        result, [_clause("según el Pliego de prescripciones técnicas del contrato")]
    )
    assert result.score_reason is not None
    assert "Pliego de prescripciones técnicas" in result.score_reason


def test_hint_preserves_existing_reason() -> None:
    result = EnrichedCoherenceResult(
        overall_score=80.0, score_missing_dimensions=["TECHNICAL"], score_reason="Base."
    )
    _annotate_missing_technical_hint(result, [_clause("conforme a las prescripciones técnicas")])
    assert result.score_reason is not None
    assert result.score_reason.startswith("Base.")
    assert "Upload the Pliego" in result.score_reason


def test_no_hint_when_not_referenced() -> None:
    result = EnrichedCoherenceResult(
        overall_score=80.0, score_missing_dimensions=["TECHNICAL"], score_reason="Base."
    )
    _annotate_missing_technical_hint(result, [_clause("el plazo de ejecución es 12 meses")])
    assert result.score_reason == "Base."


def test_no_hint_when_technical_not_missing() -> None:
    result = EnrichedCoherenceResult(
        overall_score=80.0, score_missing_dimensions=[], score_reason=None
    )
    _annotate_missing_technical_hint(result, [_clause("pliego de prescripciones técnicas")])
    assert result.score_reason is None

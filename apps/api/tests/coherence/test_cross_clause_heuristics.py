"""
Deterministic cross-clause contradiction floor for LEGAL/SCOPE (cross-document coherence).

Refers to Suite ID: TS-UD-COH-XCLAUSE-CONTRADICTION-001.
"""
from __future__ import annotations

import pytest

from src.coherence.graph.nodes import _check_legal_conflict, _check_scope_conflict
from src.coherence.graph.state import ClauseWithEmbedding, CrossClausePair
from src.coherence.models import Clause


def _cwe(clause_id: str, text: str, category: str) -> ClauseWithEmbedding:
    return ClauseWithEmbedding(
        clause=Clause(id=clause_id, text=text, data={}),
        category=category,  # type: ignore[arg-type]
    )


def _pair(a: ClauseWithEmbedding, b: ClauseWithEmbedding) -> CrossClausePair:
    return CrossClausePair(clause_a=a, clause_b=b, similarity_score=0.0, match_reason="test")


@pytest.mark.unit
def test_legal_conflict_fires_on_exemption_vs_enforcement() -> None:
    """AL-Zour pattern: one clause exempts penalties, the other enforces them."""
    a = _cwe("leg-1", "El Contratista queda exento de penalizaciones por retraso.", "LEGAL")
    b = _cwe("leg-2", "Se aplicaran penalizaciones por retraso cubiertas por el aval.", "LEGAL")
    finding = _check_legal_conflict(_pair(a, b))
    assert finding is not None
    assert finding.rule_id == "CROSS-LEGAL-CONFLICT"
    assert finding.category == "LEGAL"
    assert finding.severity == "high"


@pytest.mark.unit
def test_legal_no_conflict_when_both_enforce() -> None:
    a = _cwe("leg-1", "Se aplicaran penalizaciones por retraso.", "LEGAL")
    b = _cwe("leg-2", "El aval cubrira las penalizaciones aplicables.", "LEGAL")
    assert _check_legal_conflict(_pair(a, b)) is None


@pytest.mark.unit
def test_legal_no_conflict_without_shared_penalty_topic() -> None:
    """Both must actually discuss penalties/liability — no topic, no conflict."""
    a = _cwe("leg-1", "El contrato se rige por la ley espanola.", "LEGAL")
    b = _cwe("leg-2", "Se aplicaran penalizaciones por retraso.", "LEGAL")
    assert _check_legal_conflict(_pair(a, b)) is None


@pytest.mark.unit
def test_legal_conflict_is_order_canonical() -> None:
    """The (b,a) ordering (a.id >= b.id) yields no duplicate finding."""
    a = _cwe("leg-2", "exento de penalizaciones", "LEGAL")
    b = _cwe("leg-1", "penalizaciones aplican con aval", "LEGAL")
    assert _check_legal_conflict(_pair(a, b)) is None  # a.id 'leg-2' >= b.id 'leg-1'


@pytest.mark.unit
def test_scope_conflict_fires_on_include_vs_exclude() -> None:
    a = _cwe("sco-1", "El alcance includes el suministro del transformador.", "SCOPE")
    b = _cwe("sco-2", "El transformador is out of scope, supplied by others.", "SCOPE")
    finding = _check_scope_conflict(_pair(a, b))
    assert finding is not None
    assert finding.rule_id == "CROSS-SCOPE-CONFLICT"
    assert finding.category == "SCOPE"


@pytest.mark.unit
def test_wrong_category_returns_none() -> None:
    a = _cwe("b-1", "penalty exempt", "BUDGET")
    b = _cwe("l-2", "penalty applies with bond", "LEGAL")
    assert _check_legal_conflict(_pair(a, b)) is None
    assert _check_scope_conflict(_pair(a, b)) is None

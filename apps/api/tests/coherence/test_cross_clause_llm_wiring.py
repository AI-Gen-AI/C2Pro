"""
cross_clause_eval LLM depth-pass wiring — flag-gated, default off (ADR-017-style).

Refers to Suite ID: TS-UA-COH-XCLAUSE-LLM-WIRING-001.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.coherence.graph.cross_clause_llm import _BatchVerdict, _PairVerdict
from src.coherence.graph.nodes import cross_clause_eval
from src.coherence.graph.state import (
    ClauseWithEmbedding,
    CoherenceGraphState,
    CrossClausePair,
    EvaluationConfig,
)
from src.coherence.models import Clause

_WRAPPER_FACTORY = "src.core.ai.anthropic_wrapper.get_anthropic_wrapper"


def _cwe(clause_id: str, text: str, category: str) -> ClauseWithEmbedding:
    return ClauseWithEmbedding(clause=Clause(id=clause_id, text=text, data={}), category=category)  # type: ignore[arg-type]


_PAIR = CrossClausePair(
    clause_a=_cwe("s1", "no marker terms here", "SCOPE"),
    clause_b=_cwe("s2", "no marker terms here", "SCOPE"),
    similarity_score=0.0,
    match_reason="test",
)


def _state(*, llm_enabled: bool, low_budget: bool = False) -> CoherenceGraphState:
    return CoherenceGraphState(
        project_id="test",
        clauses=[_PAIR.clause_a.clause, _PAIR.clause_b.clause],
        cross_pairs=[_PAIR],
        config=EvaluationConfig(llm_crosscheck_enabled=llm_enabled, low_budget_mode=low_budget),
    )


def _has_llm_signal(result: dict) -> bool:
    return any(s.rule_id == "CROSS-LLM-CONTRADICTION" for s in result["cross_signals"])


@pytest.mark.unit
def test_flag_off_skips_llm_pass() -> None:
    with patch(_WRAPPER_FACTORY) as get_wrapper:
        result = cross_clause_eval(_state(llm_enabled=False))
    get_wrapper.assert_not_called()
    assert not _has_llm_signal(result)


@pytest.mark.unit
def test_low_budget_skips_llm_pass_even_when_flag_on() -> None:
    with patch(_WRAPPER_FACTORY) as get_wrapper:
        cross_clause_eval(_state(llm_enabled=True, low_budget=True))
    get_wrapper.assert_not_called()


@pytest.mark.unit
def test_flag_on_runs_llm_pass_and_adds_signal() -> None:
    wrapper = AsyncMock()
    wrapper.generate_structured.return_value = _BatchVerdict(
        verdicts=[_PairVerdict(index=0, contradicts=True, category="SCOPE", severity="high",
                               explanation="conflict")]
    )
    with patch(_WRAPPER_FACTORY, return_value=wrapper):
        result = cross_clause_eval(_state(llm_enabled=True))
    assert _has_llm_signal(result)


@pytest.mark.unit
def test_flag_on_fail_open_on_wrapper_error() -> None:
    """A depth-pass failure must not break the node — it returns findings without raising."""
    with patch(_WRAPPER_FACTORY, side_effect=RuntimeError("no api key")):
        result = cross_clause_eval(_state(llm_enabled=True))
    assert isinstance(result["cross_signals"], list)  # did not raise
    assert not _has_llm_signal(result)

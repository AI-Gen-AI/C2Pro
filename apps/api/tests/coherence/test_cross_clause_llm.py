"""
LLM cross-clause contradiction depth pass (ADR-009 cross-document coherence).

Refers to Suite ID: TS-UA-COH-XCLAUSE-LLM-001.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.coherence.graph.cross_clause_llm import (
    _BatchVerdict,
    _PairVerdict,
    llm_contradiction_signals,
)
from src.coherence.graph.state import ClauseWithEmbedding, CrossClausePair
from src.coherence.models import Clause


def _pair(a_id: str, a_text: str, b_id: str, b_text: str, category: str = "LEGAL") -> CrossClausePair:
    return CrossClausePair(
        clause_a=ClauseWithEmbedding(clause=Clause(id=a_id, text=a_text, data={}), category=category),  # type: ignore[arg-type]
        clause_b=ClauseWithEmbedding(clause=Clause(id=b_id, text=b_text, data={}), category=category),  # type: ignore[arg-type]
        similarity_score=0.0,
        match_reason="test",
    )


@pytest.mark.unit
def test_emits_signal_for_contradicting_pair() -> None:
    pairs = [_pair("l1", "exempt from penalties", "l2", "penalties apply")]
    wrapper = AsyncMock()
    wrapper.generate_structured.return_value = _BatchVerdict(
        verdicts=[_PairVerdict(index=0, contradicts=True, category="LEGAL", severity="high",
                               explanation="one exempts, one enforces")]
    )
    signals = asyncio.run(llm_contradiction_signals(pairs, wrapper=wrapper))
    assert len(signals) == 1
    assert signals[0].rule_id == "CROSS-LLM-CONTRADICTION"
    assert signals[0].category == "LEGAL"
    assert signals[0].source == "llm"
    assert signals[0].severity == "high"


@pytest.mark.unit
def test_no_signal_when_not_contradicting() -> None:
    pairs = [_pair("l1", "a", "l2", "b")]
    wrapper = AsyncMock()
    wrapper.generate_structured.return_value = _BatchVerdict(
        verdicts=[_PairVerdict(index=0, contradicts=False)]
    )
    assert asyncio.run(llm_contradiction_signals(pairs, wrapper=wrapper)) == []


@pytest.mark.unit
def test_fail_open_on_llm_error() -> None:
    """A depth-pass failure must never break /evaluate — returns [] on any error."""
    pairs = [_pair("l1", "a", "l2", "b")]
    wrapper = AsyncMock()
    wrapper.generate_structured.side_effect = RuntimeError("llm down")
    assert asyncio.run(llm_contradiction_signals(pairs, wrapper=wrapper)) == []


@pytest.mark.unit
def test_empty_pairs_makes_no_call() -> None:
    wrapper = AsyncMock()
    assert asyncio.run(llm_contradiction_signals([], wrapper=wrapper)) == []
    wrapper.generate_structured.assert_not_called()


@pytest.mark.unit
def test_out_of_range_index_is_ignored() -> None:
    pairs = [_pair("l1", "a", "l2", "b")]
    wrapper = AsyncMock()
    wrapper.generate_structured.return_value = _BatchVerdict(
        verdicts=[_PairVerdict(index=5, contradicts=True)]
    )
    assert asyncio.run(llm_contradiction_signals(pairs, wrapper=wrapper)) == []


@pytest.mark.unit
def test_max_pairs_bounds_the_batch() -> None:
    pairs = [_pair(f"a{i}", "x", f"b{i}", "y") for i in range(30)]
    wrapper = AsyncMock()
    wrapper.generate_structured.return_value = _BatchVerdict(verdicts=[])
    asyncio.run(llm_contradiction_signals(pairs, wrapper=wrapper, max_pairs=20))
    # the prompt only included 20 pairs (indices 0..19)
    prompt = wrapper.generate_structured.call_args.args[0].prompt
    assert "[19]" in prompt and "[20]" not in prompt

"""
Regression tests for Coherence v1 insufficient-evidence semantics.

Refers to Suite ID: TS-UA-COH-UC-001.
Refers to backlog_id: TASK-COH-V1-02.
"""

from uuid import uuid4

import pytest

from src.coherence.models import Clause
from src.coherence.scoring import ScoringService


def test_empty_signals_return_insufficient_evidence_result() -> None:
    """TS-UA-COH-UC-001: Empty evaluator signals withhold the score."""
    result = ScoringService().calculate_from_signals([])

    assert result.score is None
    assert result.reason == "insufficient_evidence"
    assert result.missing_dimensions == ["schedule", "budget"]


def test_poor_extraction_quality_returns_insufficient_evidence_result() -> None:
    """TS-UA-COH-UC-001: Poor extraction quality withholds the score."""
    result = ScoringService().calculate_from_signals(
        [],
        poor_extraction_quality=True,
        missing_dimensions=["schedule", "budget"],
    )

    assert result.score is None
    assert result.reason == "insufficient_evidence"
    assert result.missing_dimensions == ["schedule", "budget"]


@pytest.mark.asyncio
async def test_single_clause_llm_analysis_returns_insufficient_clauses() -> None:
    """TS-UA-COH-UC-001: Single-clause LLM analysis cannot claim 100."""
    from src.coherence.llm_integration import CoherenceLLMService

    result = await CoherenceLLMService().analyze_multi_clause_coherence(
        [Clause(id=str(uuid4()), text="Single contract clause")]
    )

    assert result.overall_coherence_score is None
    assert result.reason == "insufficient_clauses"
    assert result.cross_clause_issues == []

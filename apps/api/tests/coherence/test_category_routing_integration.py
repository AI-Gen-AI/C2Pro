"""Integration tests for CategoryRouter -> coherence coverage.

Suite ID: TS-IA-COH-ROUTING-001 — TASK-BCK-087.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from src.coherence.graph.graph import evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause


def _disable_langchain_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """TS-IA-COH-ROUTING-001 — Keep this test focused on routing coverage."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    from langchain_core.tracers import context as langchain_tracing_context
    from langsmith import run_helpers as langsmith_run_helpers
    from langsmith import utils as langsmith_utils

    @contextmanager
    def disabled_tracing_v2(*_args: object, **_kwargs: object) -> Iterator[None]:
        yield None

    monkeypatch.setattr(
        langsmith_run_helpers,
        "get_tracing_context",
        lambda: {"parent": None, "project_name": None, "enabled": False},
    )
    monkeypatch.setattr(langsmith_utils, "tracing_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "_tracing_v2_is_enabled", lambda: False)
    monkeypatch.setattr(langchain_tracing_context, "tracing_v2_enabled", disabled_tracing_v2)


@pytest.mark.asyncio
async def test_contract_prior_marks_legal_assessed_without_risk_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-IA-COH-ROUTING-001 — Contract priors keep LEGAL assessed."""
    _disable_langchain_tracing(monkeypatch)

    result = await evaluate_coherence_async(
        clauses=[
            Clause(
                id="contract-doc-1",
                text="Main agreement between the parties for construction works.",
                data={"document_type": "contract"},
            )
        ],
        project_id="routing-contract",
        config=EvaluationConfig(low_budget_mode=True),
        seed_signals=[],
        seed_coverage={},
    )

    breakdown = {item.category: item for item in result.category_breakdown}

    assert breakdown["legal"].state == "assessed_clean"
    assert breakdown["legal"].score is not None
    assert breakdown["legal"].alert_count == 0

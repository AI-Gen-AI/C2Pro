"""Integration: risk_signal_bridge → evaluate_coherence_async end-to-end.

Refers to Suite ID: TS-UA-ANA-GRAPH-001.

Unit tests in ``test_risk_signal_bridge.py`` cover the bridge in
isolation.  This file proves the seed actually propagates through the
LangGraph reducer chain into ``_build_category_breakdown`` so that a
category with extracted risks ends up as ``assessed_findings`` instead
of ``unassessed``.  Catches regressions where the seed gets silently
overwritten by the reducer.

No DB, no LLM — uses ``low_budget_mode=True`` to mirror the production
N8 call.
"""
from __future__ import annotations

import pytest

from src.analysis.adapters.graph.risk_signal_bridge import build_risk_signals
from src.coherence.graph.graph import evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause


@pytest.fixture(autouse=True)
def _disable_langchain_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same workaround used by tests/integration/document_flow/."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "false")
    try:
        from langsmith import run_helpers as langsmith_run_helpers
        from langsmith import utils as langsmith_utils

        monkeypatch.setattr(
            langsmith_run_helpers,
            "get_tracing_context",
            lambda: {"parent": None, "project_name": None, "enabled": False, "metadata": {}, "tags": []},
            raising=False,
        )
        monkeypatch.setattr(
            langsmith_utils, "tracing_is_enabled", lambda: False, raising=False
        )
    except Exception:
        pass
    try:
        from langchain_core.tracers import context as langchain_tracing_context

        monkeypatch.setattr(
            langchain_tracing_context,
            "_get_tracer_project",
            lambda: "disabled",
            raising=False,
        )
    except Exception:
        pass


def _epc_risks() -> list[dict]:
    """Three risks mirroring the live API repro: 1 LEGAL HIGH + 1 TECHNICAL HIGH + 1 LEGAL CRITICAL."""
    return [
        {
            "category": "LEGAL",
            "title": "Cross-contamination clause",
            "summary": "Default in second contract = default in first",
            "risk_score": 8,
            "impact": "CRITICAL",
            "probability": "MEDIUM",
            "source_quote": "any default or breach under the 'Second Contract' shall automatically be deemed as a default",
        },
        {
            "category": "TECHNICAL",
            "title": "Logistics from Spain to India",
            "summary": "International supply chain risk",
            "risk_score": 9,
            "impact": "HIGH",
            "probability": "HIGH",
            "source_quote": "port handling and custom clearance of Plant and Equipment",
        },
        {
            "category": "SCHEDULE",
            "title": "Effective date conditioned on three events",
            "summary": "Project start depends on three simultaneous conditions",
            "risk_score": 6,
            "impact": "HIGH",
            "probability": "MEDIUM",
            "source_quote": "Effective Date from which the Time for Completion shall be counted",
        },
    ]


@pytest.mark.asyncio
async def test_bridge_seed_promotes_legal_to_assessed_findings() -> None:
    """Reproduce the live-API symptom and prove the bridge fixes it.

    Without the seed: LEGAL state = 'unassessed', score = None.
    With the seed:    LEGAL state = 'assessed_findings', score is set.
    """
    risks = _epc_risks()
    clause = Clause(
        id="contract-epc-001",
        text="(synthetic contract body — does not matter for this test)",
        data={"document_type": "contract", "risks": risks},
    )

    bridge = build_risk_signals(risks, clause_id=clause.id)
    assert len(bridge.signals) == 3, "all three risks should convert"
    assert bridge.coverage_seed == {"LEGAL": True, "TECHNICAL": True, "TIME": True}

    result = await evaluate_coherence_async(
        clauses=[clause],
        project_id="test-project",
        config=EvaluationConfig(low_budget_mode=True),
        seed_signals=list(bridge.signals),
        seed_coverage=bridge.coverage_seed,
    )

    by_cat = {b.category: b for b in result.category_breakdown}

    # Each seeded category must end up assessed_findings with a real score.
    for legacy_name in ("legal", "technical", "schedule"):
        cat = by_cat[legacy_name]
        assert cat.state == "assessed_findings", (
            f"{legacy_name} should be assessed_findings, got {cat.state!r}"
        )
        assert cat.score is not None, (
            f"{legacy_name} should have a numeric score, got None"
        )
        assert cat.alert_count >= 1


@pytest.mark.asyncio
async def test_without_seed_legal_is_assessed_clean_by_category_prior() -> None:
    """Control: category routing now assesses LEGAL even without risk-signal seeds."""
    risks = _epc_risks()
    clause = Clause(
        id="contract-epc-001",
        text="(synthetic contract body)",
        data={"document_type": "contract", "risks": risks},
    )

    result = await evaluate_coherence_async(
        clauses=[clause],
        project_id="test-project",
        config=EvaluationConfig(low_budget_mode=True),
        # NO seeds — old behavior
    )

    by_cat = {b.category: b for b in result.category_breakdown}
    assert by_cat["legal"].state == "assessed_clean"
    assert by_cat["legal"].score is not None
    assert by_cat["legal"].alert_count == 0

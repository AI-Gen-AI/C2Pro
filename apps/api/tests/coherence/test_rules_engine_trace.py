"""
Tests for the structured RuleExecutionTrace on the deprecated v0 engine
(ADR-009 §20: rules_engine.py remove implicit defaults — Phase 1 wraps with telemetry).

Refers to Suite ID: TS-UD-COH-V2-TRACE-001.
"""
from __future__ import annotations

import logging

import pytest

from src.coherence.domain.rules_engine import (
    CoherenceContext,
    CoherenceRulesEngine,
    RuleExecutionTrace,
    ScoreCalculator,
)


@pytest.mark.unit
def test_trace_dataclass_has_required_fields() -> None:
    fields = RuleExecutionTrace.__dataclass_fields__
    assert {"rule_id", "inputs_hash", "output", "applied_default", "timestamp"} <= set(fields)


@pytest.mark.unit
def test_engine_emits_trace_for_each_rule() -> None:
    engine = CoherenceRulesEngine()
    engine.evaluate(CoherenceContext(scope_defined=False))
    traces = engine.last_traces()
    assert len(traces) >= 1
    assert any(t.applied_default is False for t in traces)


@pytest.mark.unit
def test_default_100_branch_emits_deprecation_telemetry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calc = ScoreCalculator()
    # Missing categories trigger the default-100 path.
    with caplog.at_level(logging.WARNING):
        calc.calculate({"SCOPE": 80})  # 5 missing categories will hit the default
    assert any(
        "coherence.rule_default_100_used" in r.getMessage()
        for r in caplog.records
    )

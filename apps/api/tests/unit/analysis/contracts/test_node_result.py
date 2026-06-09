"""Freeze-lock tests for the ADR-013 NodeResult contract (TASK-V3-013-02).

Verifies the execution envelope every material node must return, and that the
contract structurally forbids silent failures (FAILED without an ErrorRecord).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.analysis.domain.node_result import ErrorRecord, NodeResult, NodeStatus


def test_ok_result_is_usable():
    r = NodeResult(node="risk_extractor", status=NodeStatus.OK, confidence=0.9)
    assert r.ok and r.usable and not r.is_failure


def test_degraded_is_usable_but_not_ok():
    r = NodeResult(node="n8", status=NodeStatus.DEGRADED, degradation_reason="fallback")
    assert r.usable and not r.ok


def test_failed_requires_error_record():
    # ADR-013: a failure with no ErrorRecord is a silent failure — forbidden.
    with pytest.raises(ValidationError):
        NodeResult(node="n4", status=NodeStatus.FAILED)


def test_failed_with_error_is_valid():
    err = ErrorRecord(node="n4", error_type="ValueError", message="boom")
    r = NodeResult(node="n4", status=NodeStatus.FAILED, error=err)
    assert r.is_failure and not r.usable
    assert r.error is not None and r.error.message == "boom"


def test_skipped_is_not_usable_not_failure():
    r = NodeResult(node="n6", status=NodeStatus.SKIPPED)
    assert not r.usable and not r.is_failure


def test_extra_key_forbidden():
    with pytest.raises(ValidationError):
        NodeResult(node="n", status=NodeStatus.OK, bogus=1)


def test_frozen():
    r = NodeResult(node="n", status=NodeStatus.OK)
    with pytest.raises(ValidationError):
        r.status = NodeStatus.FAILED


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        NodeResult(node="n", status=NodeStatus.OK, confidence=2.0)


def test_status_value_set_is_frozen():
    assert {s.value for s in NodeStatus} == {"ok", "degraded", "failed", "skipped"}

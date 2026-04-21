"""
Unit tests for HITL workflow resume metrics (TASK-BCK-032).

Covers Prometheus counter/gauge/histogram behavior and the DataDog
feature-detected adapter. Metrics are verified by inspecting the
prometheus_client collector registry directly so the assertions are
independent of wire format and remain hermetic.
"""
from __future__ import annotations

from unittest import mock

import pytest

from src.core.observability import monitoring


def _counter_value(metric, **labels: str) -> float:
    """Read a labeled counter's current value via child()."""
    if not labels:
        return metric._value.get()
    return metric.labels(**labels)._value.get()


def _gauge_value(metric, **labels: str) -> float:
    return metric.labels(**labels)._value.get()


@pytest.fixture(autouse=True)
def _reset_running_totals():
    """Guarantee isolation across tests by clearing in-process counters."""
    monitoring.reset_hitl_decision_counters()
    yield
    monitoring.reset_hitl_decision_counters()


class TestCheckpointLoadErrors:
    def test_checkpoint_load_error_increments_counter(self):
        before = _counter_value(monitoring.HITL_CHECKPOINT_LOAD_ERRORS, reason="not_found")
        monitoring.record_hitl_checkpoint_load_error("not_found")
        after = _counter_value(monitoring.HITL_CHECKPOINT_LOAD_ERRORS, reason="not_found")
        assert after == before + 1

    def test_checkpoint_load_error_label_isolation(self):
        """Counters with different reasons must not collide."""
        monitoring.record_hitl_checkpoint_load_error("not_found")
        monitoring.record_hitl_checkpoint_load_error("db_error")
        nf = _counter_value(monitoring.HITL_CHECKPOINT_LOAD_ERRORS, reason="not_found")
        db = _counter_value(monitoring.HITL_CHECKPOINT_LOAD_ERRORS, reason="db_error")
        assert nf >= 1
        assert db >= 1


class TestWorkflowResumeErrors:
    def test_workflow_resume_error_increments_by_decision(self):
        before = _counter_value(monitoring.HITL_WORKFLOW_RESUME_ERRORS, decision="approve")
        monitoring.record_hitl_workflow_resume_error("approve")
        after = _counter_value(monitoring.HITL_WORKFLOW_RESUME_ERRORS, decision="approve")
        assert after == before + 1


class TestHITLDecisionAndApprovalRate:
    def test_approve_decision_sets_rate_to_one(self):
        monitoring.record_hitl_decision("tenant-a", "approve")
        assert _gauge_value(monitoring.HITL_APPROVAL_RATE, tenant_id="tenant-a") == 1.0

    def test_reject_decision_sets_rate_to_zero(self):
        monitoring.record_hitl_decision("tenant-b", "reject")
        assert _gauge_value(monitoring.HITL_APPROVAL_RATE, tenant_id="tenant-b") == 0.0

    def test_mixed_decisions_compute_ratio(self):
        monitoring.record_hitl_decision("tenant-c", "approve")
        monitoring.record_hitl_decision("tenant-c", "approve")
        monitoring.record_hitl_decision("tenant-c", "approve")
        monitoring.record_hitl_decision("tenant-c", "reject")
        # 3 of 4 approved
        assert _gauge_value(monitoring.HITL_APPROVAL_RATE, tenant_id="tenant-c") == 0.75

    def test_unknown_decision_is_ignored(self):
        """Decisions outside {approve, reject} must not perturb the counters."""
        monitoring.record_hitl_decision("tenant-d", "escalate")
        monitoring.record_hitl_decision("tenant-d", "")
        # Gauge should not have been created/updated
        assert monitoring._hitl_approve_counts["tenant-d"] == 0
        assert monitoring._hitl_reject_counts["tenant-d"] == 0

    def test_tenant_isolation(self):
        monitoring.record_hitl_decision("tenant-x", "approve")
        monitoring.record_hitl_decision("tenant-y", "reject")
        assert _gauge_value(monitoring.HITL_APPROVAL_RATE, tenant_id="tenant-x") == 1.0
        assert _gauge_value(monitoring.HITL_APPROVAL_RATE, tenant_id="tenant-y") == 0.0

    def test_decision_total_counter_increments(self):
        before = _counter_value(
            monitoring.HITL_DECISION_TOTAL, tenant_id="tenant-z", decision="approve"
        )
        monitoring.record_hitl_decision("tenant-z", "approve")
        after = _counter_value(
            monitoring.HITL_DECISION_TOTAL, tenant_id="tenant-z", decision="approve"
        )
        assert after == before + 1


class TestDatadogAdapter:
    def test_datadog_is_noop_when_disabled(self):
        """With no DD_AGENT_HOST env var, calls must be safe no-ops."""
        # The module is loaded in test env without DataDog; ensure flag is False.
        assert monitoring.DATADOG_AVAILABLE is False
        # Call all three forwarders - they must not raise.
        monitoring._datadog_increment("c2pro.test", tags=["x:1"])
        monitoring._datadog_gauge("c2pro.test", 1.0, tags=["x:1"])
        monitoring._datadog_histogram("c2pro.test", 0.5, tags=["x:1"])

    def test_datadog_forwarder_swallows_statsd_errors(self):
        """Transient statsd failures must never surface to callers."""
        fake_client = mock.Mock()
        fake_client.increment.side_effect = RuntimeError("udp_socket_down")
        fake_client.gauge.side_effect = RuntimeError("udp_socket_down")
        fake_client.histogram.side_effect = RuntimeError("udp_socket_down")

        with (
            mock.patch.object(monitoring, "_DD_STATSD", fake_client),
            mock.patch.object(monitoring, "DATADOG_AVAILABLE", True),
        ):
            # None of these should raise
            monitoring._datadog_increment("c2pro.test", tags=["a:1"])
            monitoring._datadog_gauge("c2pro.test", 1.0, tags=["a:1"])
            monitoring._datadog_histogram("c2pro.test", 0.1, tags=["a:1"])

        assert fake_client.increment.called
        assert fake_client.gauge.called
        assert fake_client.histogram.called

    def test_record_hitl_decision_forwards_to_datadog(self):
        """When DataDog is active, record_hitl_decision emits counter + gauge."""
        fake_client = mock.Mock()
        with (
            mock.patch.object(monitoring, "_DD_STATSD", fake_client),
            mock.patch.object(monitoring, "DATADOG_AVAILABLE", True),
        ):
            monitoring.record_hitl_decision("tenant-dd", "approve")

        fake_client.increment.assert_called_once()
        fake_client.gauge.assert_called_once()
        # Verify tenant + decision appear in the tags of the increment call
        _, kwargs = fake_client.increment.call_args
        assert "tenant_id:tenant-dd" in kwargs["tags"]
        assert "decision:approve" in kwargs["tags"]


class TestExistingHelpersStillFunctional:
    """Regression guard: the pre-existing helpers must continue to increment counters."""

    def test_resume_attempt_counter_increments(self):
        before = _counter_value(
            monitoring.HITL_RESUME_TOTAL, decision="approve", status="resumed"
        )
        monitoring.record_hitl_resume_attempt("approve", "resumed")
        after = _counter_value(
            monitoring.HITL_RESUME_TOTAL, decision="approve", status="resumed"
        )
        assert after == before + 1

    def test_resume_error_counter_increments(self):
        before = _counter_value(monitoring.HITL_RESUME_ERRORS, error_type="not_found")
        monitoring.record_hitl_resume_error("not_found")
        after = _counter_value(monitoring.HITL_RESUME_ERRORS, error_type="not_found")
        assert after == before + 1

    def test_resume_latency_records_observation(self):
        """Histogram _count sample must advance on every observation."""
        metric = monitoring.HITL_RESUME_LATENCY.labels(decision="approve")
        before = metric._sum.get()
        monitoring.record_hitl_resume_latency("approve", 0.123)
        after = metric._sum.get()
        assert after == pytest.approx(before + 0.123, rel=1e-6)

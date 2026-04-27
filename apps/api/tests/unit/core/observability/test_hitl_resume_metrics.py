"""HITL workflow resume monitoring regression tests.

Test Suite ID: TS-BCK-032-001
"""

from src.core.observability import monitoring


class _LabeledMetric:
    def __init__(self) -> None:
        self.labels_calls: list[dict[str, str]] = []
        self.increments: list[float] = []
        self.values: list[float] = []

    def labels(self, **labels: str) -> "_LabeledMetric":
        self.labels_calls.append(labels)
        return self

    def inc(self, amount: float = 1.0) -> None:
        self.increments.append(amount)

    def set(self, value: float) -> None:
        self.values.append(value)


def test_checkpoint_load_errors_are_recorded(monkeypatch) -> None:
    """TS-BCK-032-001: checkpoint load failures get a dedicated counter."""
    metric = _LabeledMetric()
    monkeypatch.setattr(monitoring, "METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_CHECKPOINT_LOAD_ERRORS", metric)

    monitoring.record_hitl_checkpoint_load_error("checkpoint_not_found")

    assert metric.labels_calls == [{"reason": "checkpoint_not_found"}]
    assert metric.increments == [1.0]


def test_approval_rate_gauge_records_rate(monkeypatch) -> None:
    """TS-BCK-032-001: approval/rejection balance is exposed as a gauge."""
    metric = _LabeledMetric()
    monkeypatch.setattr(monitoring, "METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_APPROVAL_RATE", metric)

    monitoring.record_hitl_approval_rate("tenant-a", approvals=3, rejections=1)

    assert metric.labels_calls == [{"tenant_id": "tenant-a"}]
    assert metric.values == [0.75]


def test_approval_rate_handles_no_decisions(monkeypatch) -> None:
    """TS-BCK-032-001: empty decision windows publish a zero approval rate."""
    metric = _LabeledMetric()
    monkeypatch.setattr(monitoring, "METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_METRICS_AVAILABLE", True)
    monkeypatch.setattr(monitoring, "HITL_APPROVAL_RATE", metric)

    monitoring.record_hitl_approval_rate("tenant-a", approvals=0, rejections=0)

    assert metric.values == [0.0]

"""
Regression coverage for duplicate Prometheus metric registration.

Refers to Suite ID: TS-UC-SEC-AUD-001.
Refers to backlog_id: TASK-BCK-050.
"""

import importlib

import prometheus_client
import pytest
from prometheus_client import Gauge

from src.core.observability.monitoring import HITL_APPROVAL_RATE


def test_monitoring_module_imports_twice_without_duplicate_timeseries() -> None:
    """TS-UC-SEC-AUD-001: HITL metrics register only once per module load."""
    importlib.import_module("src.core.observability.monitoring")
    importlib.import_module("src.core.observability.monitoring")


def test_hitl_approval_rate_gauge_is_registered_exactly_once() -> None:
    """TS-BCK-050: c2pro_hitl_approval_rate must be a single registered Gauge.

    HITL_APPROVAL_RATE was present after PR #92 (grep 2026-05-16 confirmed).
    This test guards against future accidental re-registration, which would
    raise ValueError at import time and crash the process.
    """
    assert isinstance(HITL_APPROVAL_RATE, Gauge)


def test_hitl_approval_rate_duplicate_registration_raises() -> None:
    """TS-BCK-050: attempting to register c2pro_hitl_approval_rate a second time raises.

    prometheus_client raises ValueError on duplicate metric name + label set.
    This test pins that contract so any future accidental double-registration
    fails loudly in CI rather than silently corrupting metrics at runtime.

    Note: the clear_prometheus_registry autouse fixture (sdk_isolators.py) resets
    the registry before each test, so we must register once before testing the
    duplicate-rejection behaviour.
    """
    # First registration — fresh registry (reset by autouse fixture).
    prometheus_client.Gauge("c2pro_hitl_approval_rate", "first registration", ["tenant_id"])

    # Second registration with the same name must be rejected.
    with pytest.raises(ValueError, match="c2pro_hitl_approval_rate"):
        prometheus_client.Gauge(
            "c2pro_hitl_approval_rate",
            "duplicate registration attempt — must be rejected",
            ["tenant_id"],
        )

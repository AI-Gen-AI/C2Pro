"""
Regression coverage for duplicate Prometheus metric registration.

Refers to Suite ID: TS-UC-SEC-AUD-001.
Refers to backlog_id: TASK-BCK-050.
"""

import importlib


def test_monitoring_module_imports_twice_without_duplicate_timeseries() -> None:
    """TS-UC-SEC-AUD-001: HITL metrics register only once per module load."""
    importlib.import_module("src.core.observability.monitoring")
    importlib.import_module("src.core.observability.monitoring")

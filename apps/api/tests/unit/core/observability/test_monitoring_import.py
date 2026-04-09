"""
TS-OBS-MON-001: Monitoring Import Test

Verifies that the monitoring module can be imported without syntax errors.
Refers to TASK-1476.
"""

import pytest


def test_monitoring_module_importable():
    """
    Test that src.core.observability.monitoring can be imported.
    This will fail if there are syntax errors in the module.
    """
    try:
        import src.core.observability.monitoring as monitoring
        assert monitoring is not None
    except SyntaxError as e:
        pytest.fail(f"Monitoring module has a syntax error: {e}")
    except ImportError as e:
        pytest.fail(f"Monitoring module could not be imported: {e}")

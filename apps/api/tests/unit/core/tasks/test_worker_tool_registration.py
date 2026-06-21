"""TS-UNIT-CELERY-TOOLS-001: Celery worker imports AI tool registrations."""

from __future__ import annotations

import importlib
import sys


def test_celery_worker_import_registers_analysis_ai_tools() -> None:
    """TS-UNIT-CELERY-TOOLS-001: Worker boot leaves AI tool registry populated."""
    from src.core.ai.tools.registry import get_tool_registry, reset_registry

    reset_registry()
    for module_name in [
        "src.core.tasks.celery_app",
        "src.analysis.adapters.ai.tools",
        "src.analysis.adapters.ai.tools.risk_extraction_tool",
        "src.analysis.adapters.ai.tools.wbs_extraction_tool",
    ]:
        sys.modules.pop(module_name, None)

    importlib.import_module("src.core.tasks.celery_app")

    tool_names = {name for name, _versions in get_tool_registry().list_tools()}

    assert "risk_extraction" in tool_names
    assert "wbs_extraction" in tool_names
    assert tool_names

"""
I12 - Trace Envelope Completeness (Domain)
Test Suite ID: TS-I12-OBS-DOM-001
"""

import contextvars
from typing import Optional
from uuid import uuid4

import pytest

from src.modules.observability.domain.entities import TraceContext


class _TraceContextManager:
    _current: contextvars.ContextVar[Optional[TraceContext]] = contextvars.ContextVar(
        "current_trace_context", default=None
    )

    def set_context(self, context: TraceContext) -> None:
        self._current.set(context)

    def get_context(self) -> Optional[TraceContext]:
        return self._current.get()

    def clear_context(self) -> None:
        self._current.set(None)


@pytest.fixture
def trace_context_manager() -> _TraceContextManager:
    manager = _TraceContextManager()
    manager.clear_context()
    return manager


def test_i12_trace_envelope_contains_required_metadata(
    trace_context_manager: _TraceContextManager,
) -> None:
    """Refers to I12.1: trace envelope must include run identity + metadata."""
    run_id = uuid4()
    parent_id = uuid4()
    trace = TraceContext(
        run_id=run_id,
        parent_id=parent_id,
        name="test_root_run",
        run_type="chain",
        metadata={"tenant_id": "tenant-a", "project_id": "project-x"},
    )

    trace_context_manager.set_context(trace)
    read = trace_context_manager.get_context()

    assert read is not None
    assert read.run_id == run_id
    assert read.parent_id == parent_id
    assert read.name == "test_root_run"
    assert read.run_type == "chain"
    assert read.metadata["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_i12_trace_context_propagates_through_async_calls(
    trace_context_manager: _TraceContextManager,
) -> None:
    """Refers to I12.1: async operations must preserve trace context lineage."""
    root = TraceContext(run_id=uuid4(), parent_id=None, name="root", run_type="chain")
    trace_context_manager.set_context(root)

    async def _nested() -> bool:
        nested = trace_context_manager.get_context()
        assert nested is not None
        assert nested.run_id == root.run_id
        assert nested.name == "root"
        return True

    assert await _nested() is True


"""
I12 - LangSmith Adapter Run Correlation (Application)
Test Suite ID: TS-I12-OBS-APP-001
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.modules.observability.application.ports import LangSmithAdapter


class _MockRun:
    def __init__(self, run_id: UUID, parent_run_id: UUID | None, name: str, run_type: str) -> None:
        self.id = run_id
        self.parent_run_id = parent_run_id
        self.name = name
        self.run_type = run_type
        self.inputs = None
        self.outputs = None
        self.error = None
        self.end_time = None
        self.extra_attrs = {}

    def end(self, outputs=None, error=None, **kwargs) -> None:
        self.outputs = outputs
        self.error = error
        self.end_time = datetime.now()
        self.extra_attrs.update(kwargs)


class _MockLangSmithClient:
    def __init__(self) -> None:
        self.runs: dict[UUID, _MockRun] = {}

    def create_run(self, name: str, run_type: str, inputs: dict, parent_run_id: UUID | None = None, **kwargs) -> _MockRun:
        run = _MockRun(run_id=uuid4(), parent_run_id=parent_run_id, name=name, run_type=run_type)
        run.inputs = inputs
        run.extra_attrs.update(kwargs)
        self.runs[run.id] = run
        return run

    def update_run(self, run: _MockRun, **kwargs) -> None:
        run.extra_attrs.update(kwargs)


@pytest.fixture
def adapter() -> LangSmithAdapter:
    return LangSmithAdapter(langsmith_client=_MockLangSmithClient())


@pytest.mark.asyncio
async def test_i12_adapter_creates_root_run_with_required_metadata(adapter: LangSmithAdapter) -> None:
    """Refers to I12.2: root run creation must preserve name/type/inputs and metadata."""
    run = await adapter.start_run(
        name="full_decision_flow",
        run_type="chain",
        inputs={"tenant_id": "tenant-a"},
        metadata={"trace_version": "v1"},
    )

    assert run.name == "full_decision_flow"
    assert run.run_type == "chain"
    assert run.parent_run_id is None
    assert run.inputs == {"tenant_id": "tenant-a"}


@pytest.mark.asyncio
async def test_i12_adapter_correlates_child_runs_with_parent_id(adapter: LangSmithAdapter) -> None:
    """Refers to I12.2: child runs must be linked to parent via parent_run_id."""
    parent = await adapter.start_run(name="parent", run_type="chain", inputs={})
    child = await adapter.start_run(name="child", run_type="tool", inputs={}, parent_run_id=parent.id)

    assert child.parent_run_id == parent.id


@pytest.mark.asyncio
async def test_i12_adapter_annotates_exceptions_on_end_run(adapter: LangSmithAdapter) -> None:
    """Refers to I12.2: async failures must be recorded with typed error metadata."""
    run = await adapter.start_run(name="failing_step", run_type="llm", inputs={})
    await adapter.end_run(run, error={"type": "ValueError", "message": "simulated failure"})

    assert run.error is not None
    assert run.error["type"] == "ValueError"
    assert "simulated failure" in run.error["message"]


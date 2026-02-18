"""
I12 - LangSmith Adapter Integration Contract (RED)
Test Suite ID: TS-I12-OBS-ADP-001
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.modules.observability.application.ports import LangSmithAdapter
from src.modules.observability.domain.entities import EvalMetricResult


class _MockRun:
    def __init__(self, run_id: UUID, parent_run_id: UUID | None, name: str, run_type: str, inputs: dict) -> None:
        self.id = run_id
        self.parent_run_id = parent_run_id
        self.name = name
        self.run_type = run_type
        self.inputs = inputs
        self.outputs = None
        self.error = None
        self.end_time = None
        self.extra_attrs: dict = {}

    def end(self, outputs=None, error=None, **kwargs) -> None:
        self.outputs = outputs
        self.error = error
        self.end_time = datetime.now()
        self.extra_attrs.update(kwargs)


class _RecordingLangSmithClient:
    def __init__(self) -> None:
        self.last_create_kwargs: dict | None = None
        self.last_update_kwargs: dict | None = None

    def create_run(self, name: str, run_type: str, inputs: dict, parent_run_id: UUID | None = None, **kwargs) -> _MockRun:
        self.last_create_kwargs = {
            "name": name,
            "run_type": run_type,
            "inputs": inputs,
            "parent_run_id": parent_run_id,
            **kwargs,
        }
        return _MockRun(run_id=uuid4(), parent_run_id=parent_run_id, name=name, run_type=run_type, inputs=inputs)

    def update_run(self, run, **kwargs) -> None:  # noqa: ANN001
        self.last_update_kwargs = {"run": run, **kwargs}


class _TimeoutThenSuccessClient(_RecordingLangSmithClient):
    def __init__(self) -> None:
        super().__init__()
        self.create_attempts = 0

    def create_run(self, name: str, run_type: str, inputs: dict, parent_run_id: UUID | None = None, **kwargs) -> _MockRun:
        self.create_attempts += 1
        if self.create_attempts == 1:
            raise TimeoutError("langsmith timeout")
        return super().create_run(name=name, run_type=run_type, inputs=inputs, parent_run_id=parent_run_id, **kwargs)


@pytest.mark.asyncio
async def test_i12_adapter_integration_forwards_create_run_payload_and_parent_linkage_red() -> None:
    """
    TS-I12-OBS-ADP-001:
    adapter must forward expected create payload shape and preserve parent linkage.
    """
    client = _RecordingLangSmithClient()
    adapter = LangSmithAdapter(langsmith_client=client)
    parent_id = uuid4()

    await adapter.start_run(
        name="decision_flow",
        run_type="chain",
        inputs={"tenant_id": "tenant-a", "api_key": "secret"},
        parent_run_id=parent_id,
        metadata={"project_id": "project-x", "token": "secret"},
    )

    assert client.last_create_kwargs is not None
    assert client.last_create_kwargs["name"] == "decision_flow"
    assert client.last_create_kwargs["run_type"] == "chain"
    assert client.last_create_kwargs["parent_run_id"] == parent_id
    assert client.last_create_kwargs["inputs"]["api_key"] == "[REDACTED]"
    assert client.last_create_kwargs["metadata"]["token"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_i12_adapter_integration_forwards_eval_log_payload_shape_red() -> None:
    """
    TS-I12-OBS-ADP-001:
    adapter must write eval logs with dataset and serialized eval_result payload.
    """
    client = _RecordingLangSmithClient()
    adapter = LangSmithAdapter(langsmith_client=client)
    run_id = uuid4()

    await adapter.log_eval_result(
        dataset_name="extraction_eval_dataset",
        eval_result=EvalMetricResult(metric_name="recall", value=0.91, metadata={"model_version": "v1"}),
        run_id=run_id,
    )

    assert client.last_update_kwargs is not None
    assert client.last_update_kwargs["dataset"] == "extraction_eval_dataset"
    assert client.last_update_kwargs["eval_result"]["metric_name"] == "recall"
    assert client.last_update_kwargs["eval_result"]["value"] == 0.91


@pytest.mark.asyncio
async def test_i12_adapter_integration_retries_once_on_timeout_red() -> None:
    """
    TS-I12-OBS-ADP-001:
    transient timeout during create_run should be retried once before failing.
    """
    client = _TimeoutThenSuccessClient()
    adapter = LangSmithAdapter(langsmith_client=client)

    run = await adapter.start_run(name="retry_run", run_type="chain", inputs={"tenant_id": "tenant-a"})

    assert run.name == "retry_run"
    assert client.create_attempts == 2

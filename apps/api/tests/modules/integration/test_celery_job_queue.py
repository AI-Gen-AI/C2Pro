"""
Celery job queue integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.core.tasks.celery_job_queue import CeleryJobQueue, JobDispatchResult, JobStatus


@dataclass
class _FakeAsyncResult:
    id: str
    state: str = "PENDING"
    info: dict[str, Any] | None = None


class _FakeCeleryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.results: dict[str, _FakeAsyncResult] = {}
        self._counter = 0

    def send_task(self, task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _FakeAsyncResult:
        self.calls.append((task_name, args, kwargs))
        self._counter += 1
        task_id = f"task-{self._counter}"
        result = _FakeAsyncResult(id=task_id)
        self.results[task_id] = result
        return result

    def AsyncResult(self, task_id: str) -> _FakeAsyncResult:  # noqa: N802 - Celery API style
        return self.results[task_id]


class TestCeleryJobQueue:
    """Refers to Suite ID: TS-INT-EVT-CEL-001"""

    def test_001_enqueue_document_processing_job(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        result = queue.enqueue("documents.process", args=("doc_1",))
        assert isinstance(result, JobDispatchResult)
        assert result.job_id == "task-1"

    def test_002_enqueue_with_kwargs(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        queue.enqueue("documents.process", kwargs={"tenant_id": "t1"})
        task_name, _args, kwargs = client.calls[0]
        assert task_name == "documents.process"
        assert kwargs["tenant_id"] == "t1"

    def test_003_enqueue_rejects_empty_task_name(self) -> None:
        queue = CeleryJobQueue(client=_FakeCeleryClient())
        with pytest.raises(ValueError, match="task_name is required"):
            queue.enqueue("")

    def test_004_get_status_pending(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        dispatched = queue.enqueue("documents.process")
        status = queue.get_status(dispatched.job_id)
        assert status == JobStatus.PENDING

    def test_005_get_status_started(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        dispatched = queue.enqueue("documents.process")
        client.results[dispatched.job_id].state = "STARTED"
        status = queue.get_status(dispatched.job_id)
        assert status == JobStatus.RUNNING

    def test_006_get_status_success(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        dispatched = queue.enqueue("documents.process")
        client.results[dispatched.job_id].state = "SUCCESS"
        status = queue.get_status(dispatched.job_id)
        assert status == JobStatus.SUCCESS

    def test_007_get_status_failure(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        dispatched = queue.enqueue("documents.process")
        client.results[dispatched.job_id].state = "FAILURE"
        status = queue.get_status(dispatched.job_id)
        assert status == JobStatus.FAILED

    def test_008_get_status_unknown_maps_to_unknown(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        dispatched = queue.enqueue("documents.process")
        client.results[dispatched.job_id].state = "SOMETHING_ELSE"
        status = queue.get_status(dispatched.job_id)
        assert status == JobStatus.UNKNOWN

    def test_009_retry_job_requeues_with_original_name(self) -> None:
        client = _FakeCeleryClient()
        queue = CeleryJobQueue(client=client)
        queue.enqueue("documents.process", args=("doc_1",), kwargs={"tenant_id": "t1"})
        retried = queue.retry_job("documents.process", args=("doc_1",), kwargs={"tenant_id": "t1"})
        assert retried.job_id == "task-2"
        assert client.calls[-1][0] == "documents.process"

    def test_010_dispatch_result_exposes_queue_name(self) -> None:
        queue = CeleryJobQueue(client=_FakeCeleryClient(), queue_name="critical")
        dispatched = queue.enqueue("documents.process")
        assert dispatched.queue_name == "critical"

    def test_011_get_status_requires_job_id(self) -> None:
        queue = CeleryJobQueue(client=_FakeCeleryClient())
        with pytest.raises(ValueError, match="job_id is required"):
            queue.get_status("")

    def test_012_retry_job_requires_task_name(self) -> None:
        queue = CeleryJobQueue(client=_FakeCeleryClient())
        with pytest.raises(ValueError, match="task_name is required"):
            queue.retry_job("")

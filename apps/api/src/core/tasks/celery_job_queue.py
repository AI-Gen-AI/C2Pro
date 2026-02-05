"""
Celery job queue adapter.

Refers to Suite ID: TS-INT-EVT-CEL-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class CeleryAsyncResult(Protocol):
    """Minimal celery async result contract."""

    id: str
    state: str


class CeleryClient(Protocol):
    """Minimal celery client contract."""

    def send_task(self, task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> CeleryAsyncResult: ...

    def AsyncResult(self, task_id: str) -> CeleryAsyncResult: ...  # noqa: N802


class JobStatus(str, Enum):
    """Normalized job statuses."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JobDispatchResult:
    """Job dispatch response."""

    job_id: str
    queue_name: str


class CeleryJobQueue:
    """Queue adapter around Celery send_task / AsyncResult APIs."""

    def __init__(self, client: CeleryClient, queue_name: str = "default") -> None:
        self._client = client
        self._queue_name = queue_name

    def enqueue(
        self,
        task_name: str,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> JobDispatchResult:
        if not task_name:
            raise ValueError("task_name is required")
        result = self._client.send_task(
            task_name=task_name,
            args=args or (),
            kwargs=kwargs or {},
        )
        return JobDispatchResult(job_id=result.id, queue_name=self._queue_name)

    def retry_job(
        self,
        task_name: str,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> JobDispatchResult:
        if not task_name:
            raise ValueError("task_name is required")
        return self.enqueue(task_name=task_name, args=args, kwargs=kwargs)

    def get_status(self, job_id: str) -> JobStatus:
        if not job_id:
            raise ValueError("job_id is required")
        state = self._client.AsyncResult(job_id).state
        mapping = {
            "PENDING": JobStatus.PENDING,
            "RECEIVED": JobStatus.RUNNING,
            "STARTED": JobStatus.RUNNING,
            "SUCCESS": JobStatus.SUCCESS,
            "FAILURE": JobStatus.FAILED,
            "RETRY": JobStatus.RUNNING,
        }
        return mapping.get(state, JobStatus.UNKNOWN)

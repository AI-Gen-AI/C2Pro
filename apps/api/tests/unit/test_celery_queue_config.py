"""TS-OPS-CELERY-QUEUE-001

Regression checks for Celery queue wiring used by asynchronous document ingestion.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.core.tasks.celery_app import celery_app
from src.core.tasks.ingestion_tasks import (
    RAG_READINESS_MAX_RETRIES,
    process_document_analysis_async,
)
from src.core.tenants.types import TenantId


class _RetrySignal(BaseException):
    """Test double for Celery's retry control-flow exception."""


_REQUIRED_TASK_MODULES = {
    "src.core.tasks.ingestion_tasks",
    "src.core.tasks.budget_alerts",
    "src.core.tasks.project_graph_tasks",
    "src.core.tasks.snapshot_tasks",
    "src.core.tasks.snapshot_retention",
}


def test_celery_include_covers_all_registered_task_modules() -> None:
    """TASK-BCK-077: every module containing @celery_app.task decorators must be
    in the `include` list so workers auto-discover them on startup.

    Reads celery_app.py as a meta-test because celery_app is replaced by a
    _DummyCelery stub in tests (_bootstrap.py) and conf.include is lazy.
    """
    from pathlib import Path

    celery_app_source = (
        Path(__file__).parent.parent.parent
        / "src" / "core" / "tasks" / "celery_app.py"
    )
    content = celery_app_source.read_text(encoding="utf-8")
    missing = {m for m in _REQUIRED_TASK_MODULES if f'"{m}"' not in content}
    assert not missing, (
        f"Celery include list in celery_app.py missing task modules: {missing}"
    )


def test_document_ingestion_uses_document_parsing_default_queue() -> None:
    """TS-OPS-CELERY-QUEUE-001 keeps worker health checks aligned with Celery routing."""
    assert celery_app.conf.task_default_queue == "document_parsing"


def test_document_analysis_task_routes_to_worker_queue() -> None:
    """TS-OPS-CELERY-QUEUE-001 keeps full analysis on the consumed worker queue."""
    assert process_document_analysis_async.name == "documents.analyze_document"
    assert process_document_analysis_async.queue == "document_parsing"
    assert celery_app.conf.task_default_queue == process_document_analysis_async.queue


def test_document_analysis_task_normalizes_tenant_once(monkeypatch) -> None:
    """TS-OPS-CELERY-QUEUE-001 normalizes serialized tenant before analysis ports."""
    from src.core.tasks import ingestion_tasks

    raw_tenant_id = str(uuid4())
    document_id = str(uuid4())
    normalized_tenant_id = TenantId(uuid4())
    normalize = Mock(return_value=normalized_tenant_id)
    captured: dict[str, object] = {}

    async def fake_run_document_analysis(**kwargs):
        captured.update(kwargs)
        return {"status": "completed"}

    monkeypatch.setattr(ingestion_tasks, "require_tenant_id", normalize, raising=False)
    monkeypatch.setattr(
        ingestion_tasks,
        "_run_document_analysis",
        fake_run_document_analysis,
    )

    result = ingestion_tasks.process_document_analysis_async(
        SimpleNamespace(request=SimpleNamespace(id="task-1")),
        tenant_id=raw_tenant_id,
        document_id=document_id,
    )

    normalize.assert_called_once_with(raw_tenant_id)
    assert captured["tenant_id"] is normalized_tenant_id
    assert result == {"status": "completed"}


@pytest.mark.parametrize(("retries", "expected_countdown"), [(0, 1), (1, 2), (2, 4)])
def test_document_analysis_retries_unready_rag_before_running_graph(
    monkeypatch,
    retries: int,
    expected_countdown: int,
) -> None:
    """TS-UD-OPS-DOCFLOW-B-001: zero chunks retry with exponential backoff before DLQ."""
    from src.core.tasks import ingestion_tasks

    tenant_id = str(uuid4())
    document_id = str(uuid4())
    dlq_push = AsyncMock()
    retry = Mock(side_effect=_RetrySignal())

    async def raise_rag_unavailable(**_kwargs):
        raise ingestion_tasks.RagChunksUnavailableError("RAG chunks unavailable")

    monkeypatch.setattr(ingestion_tasks, "_run_document_analysis", raise_rag_unavailable)
    monkeypatch.setattr(ingestion_tasks, "_push_trigger_failure_to_dlq", dlq_push)

    with pytest.raises(_RetrySignal):
        ingestion_tasks.process_document_analysis_async(
            SimpleNamespace(
                request=SimpleNamespace(id="task-rag-gate", retries=retries),
                retry=retry,
            ),
            tenant_id=tenant_id,
            document_id=document_id,
        )

    retry.assert_called_once()
    assert retry.call_args.kwargs["countdown"] == expected_countdown
    assert retry.call_args.kwargs["max_retries"] == RAG_READINESS_MAX_RETRIES
    dlq_push.assert_not_awaited()


def test_document_analysis_routes_unready_rag_to_dlq_after_final_retry(monkeypatch) -> None:
    """TS-UD-OPS-DOCFLOW-B-001: retry exhaustion routes zero chunks to DLQ, never the graph."""
    from src.core.tasks import ingestion_tasks

    tenant_id = str(uuid4())
    document_id = str(uuid4())
    dlq_push = AsyncMock()
    retry = Mock()

    async def raise_rag_unavailable(**_kwargs):
        raise ingestion_tasks.RagChunksUnavailableError("RAG chunks unavailable")

    monkeypatch.setattr(ingestion_tasks, "_run_document_analysis", raise_rag_unavailable)
    monkeypatch.setattr(ingestion_tasks, "_push_trigger_failure_to_dlq", dlq_push)

    result = ingestion_tasks.process_document_analysis_async(
        SimpleNamespace(
            request=SimpleNamespace(
                id="task-rag-gate", retries=RAG_READINESS_MAX_RETRIES
            ),
            retry=retry,
        ),
        tenant_id=tenant_id,
        document_id=document_id,
    )

    assert result == {
        "status": "routed_to_dlq",
        "document_id": document_id,
        "reason": "rag_chunks_unavailable",
    }
    retry.assert_not_called()
    dlq_push.assert_awaited_once()

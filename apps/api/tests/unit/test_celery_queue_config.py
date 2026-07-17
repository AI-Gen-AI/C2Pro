"""TS-OPS-CELERY-QUEUE-001

Regression checks for Celery queue wiring used by asynchronous document ingestion.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from src.core.tasks.celery_app import celery_app
from src.core.tasks.ingestion_tasks import process_document_analysis_async
from src.core.tenants.types import TenantId


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

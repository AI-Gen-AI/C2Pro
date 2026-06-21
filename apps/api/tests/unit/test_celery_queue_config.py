"""TS-OPS-CELERY-QUEUE-001

Regression checks for Celery queue wiring used by asynchronous document ingestion.
"""

from __future__ import annotations

from src.core.tasks.celery_app import celery_app
from src.core.tasks.ingestion_tasks import process_document_analysis_async


def test_document_ingestion_uses_document_parsing_default_queue() -> None:
    """TS-OPS-CELERY-QUEUE-001 keeps worker health checks aligned with Celery routing."""
    assert celery_app.conf.task_default_queue == "document_parsing"


def test_document_analysis_task_routes_to_worker_queue() -> None:
    """TS-OPS-CELERY-QUEUE-001 keeps full analysis on the consumed worker queue."""
    assert process_document_analysis_async.name == "documents.analyze_document"
    assert process_document_analysis_async.queue == "document_parsing"
    assert celery_app.conf.task_default_queue == process_document_analysis_async.queue

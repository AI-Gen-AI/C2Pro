"""TS-OPS-CELERY-QUEUE-001

Regression checks for Celery queue wiring used by asynchronous document ingestion.
"""

from __future__ import annotations

from src.core.tasks.celery_app import celery_app


def test_document_ingestion_uses_document_parsing_default_queue() -> None:
    """TS-OPS-CELERY-QUEUE-001 keeps worker health checks aligned with Celery routing."""
    assert celery_app.conf.task_default_queue == "document_parsing"

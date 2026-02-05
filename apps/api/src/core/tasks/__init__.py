"""
C2Pro - Core Tasks Module

Infraestructura de background tasks: Celery app y task definitions.
"""

from src.core.tasks.celery_app import celery_app
try:
    from src.core.tasks.budget_alerts import run_budget_alerts
except Exception:  # pragma: no cover - optional runtime dependency graph
    run_budget_alerts = None  # type: ignore[assignment]

try:
    from src.core.tasks.ingestion_tasks import process_document_async
except Exception:  # pragma: no cover - optional runtime dependency graph
    process_document_async = None  # type: ignore[assignment]

__all__ = [
    "celery_app",
    "run_budget_alerts",
    "process_document_async",
]

"""
C2Pro - Core Tasks Module

Infraestructura de background tasks: Celery app y task definitions.
"""

from src.core.tasks.celery_app import celery_app
from src.core.tasks.budget_alerts import run_budget_alerts
from src.core.tasks.ingestion_tasks import process_document_async

__all__ = [
    "celery_app",
    "run_budget_alerts",
    "process_document_async",
]

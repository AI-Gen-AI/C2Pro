"""
C2Pro - Celery Application Factory

This module configures and exposes the Celery application instance.
It sets up Redis as the broker and result backend and configures task
auto-discovery.

This is the entry point for Celery workers.
Refers to Suite ID: TS-OPS-CELERY-QUEUE-001.
"""

from celery import Celery

import src.analysis.adapters.ai.tools  # noqa: F401 - registers @register_tool classes for workers
from src.config import settings

# --- Celery Application Instance ---

# How to run a worker for this app:
# From project root: celery -A apps.api.src.core.tasks.celery_app.celery_app worker --loglevel=info -P gevent
# Inside Docker/apps/api: celery -A src.core.tasks.celery_app.celery_app worker --loglevel=info
#
# The -P gevent flag is recommended for I/O bound tasks (like API calls).

celery_app = Celery(
    "c2pro_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.analysis.adapters.ai.tools",
        "src.core.tasks.ingestion_tasks",
        "src.core.tasks.budget_alerts",
        "src.core.tasks.project_graph_tasks",
        "src.core.tasks.snapshot_tasks",
        "src.core.tasks.snapshot_retention",
    ],
)

# --- Configuration ---

celery_app.conf.update(
    # Broker settings
    broker_connection_retry_on_startup=True,
    # Task settings
    task_default_queue="document_parsing",
    task_default_exchange="document_parsing",
    task_default_routing_key="document_parsing",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # Expire results after 1 hour
    task_track_started=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # Ensures workers only take one task at a time (good for long-running tasks)
    # Beat schedule (periodic tasks)
    beat_schedule={
        "budget-alerts-every-10-mins": {
            "task": "budget_alerts.run",
            "schedule": 600.0,
        },
        "project-snapshots-daily": {
            "task": "project_snapshots.enqueue_daily",
            "schedule": 86400.0,
        },
        "project-snapshots-retention": {
            "task": "project_snapshots.retention",
            "schedule": 86400.0,
        },
    },
)

if __name__ == "__main__":
    celery_app.start()

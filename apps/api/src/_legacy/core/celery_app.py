"""
C2Pro - Celery Application Factory

This module configures and exposes the Celery application instance.
It sets up Redis as the broker and result backend and configures task
auto-discovery.

This is the entry point for Celery workers.
"""

from celery import Celery
from src.config import settings

# --- Celery Application Instance ---

# How to run a worker for this app (from the project root):
# celery -A apps.api.src.core.celery_app.celery_app worker --loglevel=info -P gevent
#
# The -P gevent flag is recommended for I/O bound tasks (like API calls).

celery_app = Celery(
    "c2pro_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "apps.api.src.tasks.ingestion_tasks",
        "apps.api.src.tasks.budget_alerts",
    ],
)

# --- Configuration ---

celery_app.conf.update(
    # Broker settings
    broker_connection_retry_on_startup=True,

    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # Expire results after 1 hour
    task_track_started=True,

    # Worker settings
    worker_prefetch_multiplier=1, # Ensures workers only take one task at a time (good for long-running tasks)

    # Beat schedule (periodic tasks)
    beat_schedule={
        "budget-alerts-every-10-mins": {
            "task": "budget_alerts.run",
            "schedule": 600.0,
        }
    },
)

if __name__ == "__main__":
    celery_app.start()

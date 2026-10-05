"""Production Celery entrypoint with C2Pro structured logging bootstrap.

Celery imports this module before loading the canonical app.  Configuring
structlog here prevents worker task exceptions from falling back to development
console rendering while keeping the canonical Celery app itself unchanged.
"""

from src.core.observability.monitoring import configure_logging

configure_logging()

from src.core.tasks.celery_app import celery_app  # noqa: E402

__all__ = ["celery_app"]

"""
Celery task for periodic budget monitoring and alerts.

Note: BudgetMonitor service is not yet implemented.
This is a placeholder task that will be expanded when the budget alerting
feature is fully developed.
"""

import logging

from src.core.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="budget_alerts.run", bind=True)
def run_budget_alerts(self) -> dict:
    """
    Periodic task to check budget thresholds and send alerts.

    Currently a no-op placeholder. Will be implemented when the
    BudgetMonitor service is developed.
    """
    logger.info("budget_alerts.run task executed (no-op placeholder)")
    return {"status": "ok", "message": "Budget monitoring not yet implemented"}

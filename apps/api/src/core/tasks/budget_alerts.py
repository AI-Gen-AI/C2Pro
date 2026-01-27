"""
Celery task for periodic budget monitoring and alerts.
"""

import asyncio
import logging

from src.core.tasks.celery_app import celery_app
from src.core.database import close_db, init_db
from src.services.budget_alerts import BudgetMonitor

logger = logging.getLogger(__name__)


@celery_app.task(name="budget_alerts.run", bind=True)
def run_budget_alerts(self) -> dict:
    async def _run() -> dict:
        await init_db()
        monitor = BudgetMonitor()
        await monitor.run()
        await close_db()
        return {"status": "ok"}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("budget_alerts_task_failed", error=str(exc))
        return {"status": "error", "message": str(exc)}
